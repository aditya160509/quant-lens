#!/usr/bin/env node

/**
 * Extract Studio V2 frontend API call sites with the TypeScript compiler AST.
 *
 * This helper intentionally emits JSON only. The Python inventory generator
 * owns backend route matching and Markdown rendering.
 */

import fs from "node:fs";
import path from "node:path";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";

const scriptDirectory = path.dirname(fileURLToPath(import.meta.url));
const repositoryRoot = path.resolve(scriptDirectory, "../..");
const require = createRequire(import.meta.url);
const ts = require(path.join(repositoryRoot, "frontend/node_modules/typescript"));

const sourceRoots = [
  path.join(repositoryRoot, "frontend/src/app/studio"),
  path.join(repositoryRoot, "frontend/src/components/studio-v2"),
  path.join(repositoryRoot, "frontend/src/hooks/studio"),
];
const sourceExtensions = new Set([".js", ".jsx", ".ts", ".tsx"]);
const methodByCallee = new Map([
  ["get", "GET"],
  ["post", "POST"],
  ["put", "PUT"],
  ["remove", "DELETE"],
  ["removeRequest", "DELETE"],
  ["runRequest", "POST"],
]);

function listSourceFiles(directory) {
  if (!fs.existsSync(directory)) return [];
  const files = [];
  for (const entry of fs.readdirSync(directory, { withFileTypes: true })) {
    const absolute = path.join(directory, entry.name);
    if (entry.isDirectory()) {
      if (entry.name !== "__tests__") files.push(...listSourceFiles(absolute));
      continue;
    }
    if (!sourceExtensions.has(path.extname(entry.name))) continue;
    if (/\.(?:test|spec)\.[jt]sx?$/.test(entry.name)) continue;
    files.push(absolute);
  }
  return files.sort();
}

function scriptKind(filePath) {
  if (filePath.endsWith(".tsx")) return ts.ScriptKind.TSX;
  if (filePath.endsWith(".ts")) return ts.ScriptKind.TS;
  if (filePath.endsWith(".jsx")) return ts.ScriptKind.JSX;
  return ts.ScriptKind.JS;
}

function calleeName(expression, sourceFile) {
  if (ts.isIdentifier(expression)) return expression.text;
  if (ts.isPropertyAccessExpression(expression)) {
    return `${expression.expression.getText(sourceFile)}.${expression.name.text}`;
  }
  return expression.getText(sourceFile);
}

function functionName(node, sourceFile) {
  if ((ts.isFunctionDeclaration(node) || ts.isFunctionExpression(node)) && node.name) {
    return node.name.text;
  }
  if (ts.isMethodDeclaration(node) && node.name) return node.name.getText(sourceFile);
  if (ts.isArrowFunction(node) || ts.isFunctionExpression(node)) {
    if (ts.isVariableDeclaration(node.parent) && ts.isIdentifier(node.parent.name)) {
      return node.parent.name.text;
    }
    const call = ts.isCallExpression(node.parent) ? node.parent : null;
    if (call && ts.isVariableDeclaration(call.parent) && ts.isIdentifier(call.parent.name)) {
      return call.parent.name.text;
    }
    if (call) {
      const callbackOwner = calleeName(call.expression, sourceFile).split(".").pop();
      if (["useEffect", "useMemo", "then", "catch", "finally"].includes(callbackOwner)) {
        return callbackOwner;
      }
    }
    if (
      ts.isJsxExpression(node.parent)
      && ts.isJsxAttribute(node.parent.parent)
    ) {
      return node.parent.parent.name.getText(sourceFile);
    }
  }
  return null;
}

function enclosingFunction(node, sourceFile) {
  let current = node.parent;
  while (current) {
    if (ts.isFunctionLike(current)) {
      const name = functionName(current, sourceFile);
      if (name) return { name, node: current };
    }
    current = current.parent;
  }
  return null;
}

function ownerName(sourceFile, filePath) {
  if (sourceKind(filePath) === "hook") return path.basename(filePath, path.extname(filePath));
  for (const statement of sourceFile.statements) {
    if (ts.isFunctionDeclaration(statement) && statement.name) return statement.name.text;
  }
  return path.basename(filePath, path.extname(filePath));
}

function sourceKind(filePath) {
  const normalized = filePath.split(path.sep).join("/");
  if (normalized.includes("/hooks/studio/")) return "hook";
  if (normalized.includes("/app/studio/")) return "page";
  return "component";
}

function collectContext(sourceFile) {
  const variables = new Map();
  const invocations = new Map();
  const functionParameters = new Map();

  function visit(node) {
    if (ts.isVariableDeclaration(node) && ts.isIdentifier(node.name) && node.initializer) {
      const values = variables.get(node.name.text) || [];
      values.push(node.initializer);
      variables.set(node.name.text, values);
    }
    if (ts.isFunctionLike(node)) {
      const name = functionName(node, sourceFile);
      if (name) functionParameters.set(name, node.parameters.map((parameter) => parameter.name.getText(sourceFile)));
    }
    if (ts.isCallExpression(node) && ts.isIdentifier(node.expression)) {
      const values = invocations.get(node.expression.text) || [];
      values.push(node.arguments);
      invocations.set(node.expression.text, values);
    }
    ts.forEachChild(node, visit);
  }
  visit(sourceFile);
  return { variables, invocations, functionParameters };
}

function unique(values) {
  return [...new Set(values)];
}

function possibleStrings(expression, context, sourceFile, seen = new Set()) {
  if (!expression) return [];
  if (ts.isParenthesizedExpression(expression)) {
    return possibleStrings(expression.expression, context, sourceFile, seen);
  }
  if (ts.isStringLiteralLike(expression)) return [expression.text];
  if (ts.isConditionalExpression(expression)) {
    return unique([
      ...possibleStrings(expression.whenTrue, context, sourceFile, seen),
      ...possibleStrings(expression.whenFalse, context, sourceFile, seen),
    ]);
  }
  if (ts.isIdentifier(expression)) {
    if (seen.has(expression.text)) return [];
    const nextSeen = new Set(seen);
    nextSeen.add(expression.text);
    const values = [];
    for (const initializer of context.variables.get(expression.text) || []) {
      values.push(...possibleStrings(initializer, context, sourceFile, nextSeen));
    }
    if (values.length) return unique(values);

    const enclosing = enclosingFunction(expression, sourceFile);
    if (!enclosing) return [];
    const parameters = context.functionParameters.get(enclosing.name) || [];
    const index = parameters.indexOf(expression.text);
    if (index < 0) return [];
    for (const argumentsList of context.invocations.get(enclosing.name) || []) {
      values.push(...possibleStrings(argumentsList[index], context, sourceFile, nextSeen));
    }
    return unique(values);
  }
  return [];
}

function placeholderName(expression, sourceFile) {
  if (
    ts.isCallExpression(expression)
    && ts.isIdentifier(expression.expression)
    && expression.expression.text === "encodeURIComponent"
    && expression.arguments.length
  ) {
    return expression.arguments[0].getText(sourceFile);
  }
  return expression.getText(sourceFile).replace(/\s+/g, " ");
}

function renderPathExpression(expression, context, sourceFile) {
  if (ts.isStringLiteralLike(expression)) return [expression.text];
  if (!ts.isTemplateExpression(expression)) return [];
  let paths = [expression.head.text];
  for (const span of expression.templateSpans) {
    const known = possibleStrings(span.expression, context, sourceFile);
    const replacements = known.length ? known : [`{${placeholderName(span.expression, sourceFile)}}`];
    paths = paths.flatMap((prefix) => replacements.map((replacement) => `${prefix}${replacement}${span.literal.text}`));
  }
  return unique(paths);
}

function apiPath(pathValue) {
  const index = pathValue.indexOf("/api/v2/");
  return index >= 0 ? pathValue.slice(index) : null;
}

function fetchMethod(call, sourceFile) {
  const options = call.arguments[1];
  if (!options || !ts.isObjectLiteralExpression(options)) return "GET";
  for (const property of options.properties) {
    if (!ts.isPropertyAssignment(property) || property.name.getText(sourceFile).replace(/["']/g, "") !== "method") continue;
    const values = possibleStrings(property.initializer, { variables: new Map(), invocations: new Map(), functionParameters: new Map() }, sourceFile);
    if (values.length) return values[0].toUpperCase();
  }
  return "GET";
}

function requestKey(call, sourceFile) {
  for (const argument of call.arguments) {
    if (!ts.isObjectLiteralExpression(argument)) continue;
    for (const property of argument.properties) {
      if (!ts.isPropertyAssignment(property)) continue;
      if (property.name.getText(sourceFile).replace(/["']/g, "") !== "key") continue;
      return property.initializer.getText(sourceFile).replace(/^(["'`])|(["'`])$/g, "");
    }
  }
  return null;
}

function enclosingStatement(node) {
  let current = node;
  while (current && !ts.isStatement(current)) current = current.parent;
  return current;
}

function setterNames(text) {
  const matches = [];
  for (const match of text.matchAll(/\b(set[A-Z][A-Za-z0-9_]*|store\.set[A-Z][A-Za-z0-9_]*)\s*\(/g)) {
    matches.push(match[1]);
  }
  return unique(matches).filter((name) => !["setTimeout", "setInterval"].includes(name)).slice(0, 6);
}

function responseAndErrorConsumers(call, protocol, sourceFile, owner, localFunction, key) {
  if (protocol === "WS") {
    return {
      responseConsumer: "participants, events, and connectionState",
      errorConsumer: "socket onerror/onclose and reconnect state",
    };
  }
  const enclosing = localFunction?.node || null;
  const functionText = enclosing ? enclosing.getText(sourceFile) : "";
  const statement = enclosingStatement(call);
  const statementText = statement ? statement.getText(sourceFile) : "";
  const setters = setterNames(`${statementText}\n${functionText}`);
  const responseSetters = setters.filter((name) => !name.endsWith("Error"));
  const errorSetters = setters.filter((name) => name.endsWith("Error"));
  const isFetch = calleeName(call.expression, sourceFile).split(".").pop() === "fetch";

  let responseConsumer;
  if (isFetch) {
    responseConsumer = responseSetters.length ? responseSetters.join(", ") : `${localFunction?.name || owner} local response`;
  } else {
    const state = key ? `request state ${key}` : "shared request state";
    if (responseSetters.length) responseConsumer = `${state}; ${responseSetters.join(", ")}`;
    else if (/URL\.createObjectURL\s*\(/.test(functionText)) responseConsumer = `${state}; browser download`;
    else if (/\breturn\b/.test(functionText)) responseConsumer = `${state}; caller return value`;
    else responseConsumer = `${state}; response ignored`;
  }

  let errorConsumer;
  if (isFetch) {
    errorConsumer = /!\s*response\.ok/.test(functionText)
      ? "local status check throws Error"
      : "native fetch rejection";
  } else if (/\.catch\s*\(\s*\(\s*\)\s*=>\s*\{\s*\}\s*\)/.test(statementText)) {
    errorConsumer = "normalized request error, then swallowed locally";
  } else if (/\.catch\s*\(/.test(statementText)) {
    errorConsumer = errorSetters.length
      ? `normalized request error handled by ${errorSetters.join(", ")}`
      : "normalized request error handled locally";
  } else if (/catch\s*\([^)]*\)[\s\S]*?setError\s*\(/.test(functionText)) {
    errorConsumer = `${errorSetters.join(", ") || "domain setError"} and rethrow`;
  } else if (sourceFile.text.includes("<InlineError") || sourceFile.text.includes("requestError")) {
    errorConsumer = "normalized request error surfaced by component/store";
  } else {
    errorConsumer = "normalized request error propagated to caller";
  }
  return { responseConsumer, errorConsumer };
}

function lineNumber(sourceFile, node) {
  return sourceFile.getLineAndCharacterOfPosition(node.getStart(sourceFile)).line + 1;
}

function extractFile(filePath) {
  const text = fs.readFileSync(filePath, "utf8");
  const sourceFile = ts.createSourceFile(filePath, text, ts.ScriptTarget.Latest, true, scriptKind(filePath));
  const context = collectContext(sourceFile);
  const owner = ownerName(sourceFile, filePath);
  const kind = sourceKind(filePath);
  const relativeFile = path.relative(repositoryRoot, filePath).split(path.sep).join("/");
  const calls = [];
  const coveredPathExpressions = new Set();

  function pathValues(expression) {
    const values = renderPathExpression(expression, context, sourceFile);
    if (values.some((value) => apiPath(value))) {
      coveredPathExpressions.add(expression.getStart(sourceFile));
    }
    return values;
  }

  function pushCall(node, call, protocol, method, pathValue, localFunction, key = null) {
    const normalizedPath = apiPath(pathValue);
    if (!normalizedPath) return;
    const consumers = responseAndErrorConsumers(call, protocol, sourceFile, owner, localFunction, key);
    calls.push({
      file: relativeFile,
      line: lineNumber(sourceFile, node),
      sourceKind: kind,
      owner,
      hookMethod: localFunction?.name && localFunction.name !== owner ? localFunction.name : "component body",
      protocol,
      method,
      path: normalizedPath,
      requestKey: key,
      ...consumers,
    });
  }

  function visit(node) {
    if (ts.isCallExpression(node)) {
      const fullCallee = calleeName(node.expression, sourceFile);
      const shortCallee = fullCallee.split(".").pop();
      const method = shortCallee === "fetch" ? fetchMethod(node, sourceFile) : methodByCallee.get(shortCallee);
      if (method && node.arguments.length) {
        const paths = pathValues(node.arguments[0]);
        const localFunction = enclosingFunction(node, sourceFile);
        const key = shortCallee === "fetch" ? null : requestKey(node, sourceFile);
        for (const pathValue of paths) pushCall(node, node, "HTTP", method, pathValue, localFunction, key);
      }
    }
    if (
      ts.isNewExpression(node)
      && ts.isIdentifier(node.expression)
      && node.expression.text === "WebSocket"
      && node.arguments?.length
    ) {
      const argument = node.arguments[0];
      if (ts.isCallExpression(argument) && ts.isIdentifier(argument.expression)) {
        const helperName = argument.expression.text;
        for (const statement of sourceFile.statements) {
          if (!ts.isFunctionDeclaration(statement) || statement.name?.text !== helperName || !statement.body) continue;
          for (const child of statement.body.statements) {
            if (!ts.isReturnStatement(child) || !child.expression) continue;
            for (const pathValue of pathValues(child.expression)) {
              pushCall(node, node, "WS", "WS", pathValue, enclosingFunction(node, sourceFile));
            }
          }
        }
      }
    }
    ts.forEachChild(node, visit);
  }
  visit(sourceFile);
  const uncovered = [];
  function auditPathExpressions(node) {
    const isPathExpression = ts.isStringLiteralLike(node) || ts.isTemplateExpression(node);
    if (isPathExpression && node.getText(sourceFile).includes("/api/v2/")) {
      const start = node.getStart(sourceFile);
      if (!coveredPathExpressions.has(start)) uncovered.push(lineNumber(sourceFile, node));
    }
    ts.forEachChild(node, auditPathExpressions);
  }
  auditPathExpressions(sourceFile);
  if (uncovered.length) {
    throw new Error(
      `Unclassified /api/v2 path expression(s) in ${relativeFile}:${unique(uncovered).join(",")}`,
    );
  }
  return calls;
}

function importedHookBindings(sourceFile, hookNames) {
  const bindings = new Map();
  for (const statement of sourceFile.statements) {
    if (!ts.isImportDeclaration(statement) || !ts.isStringLiteral(statement.moduleSpecifier)) continue;
    const moduleName = statement.moduleSpecifier.text;
    const moduleHook = path.basename(moduleName);
    const isHookModule = moduleName.includes("hooks/studio") || hookNames.has(moduleHook);
    if (!isHookModule || !statement.importClause) continue;

    if (statement.importClause.name && hookNames.has(moduleHook)) {
      bindings.set(statement.importClause.name.text, moduleHook);
    }
    const namedBindings = statement.importClause.namedBindings;
    if (!namedBindings || !ts.isNamedImports(namedBindings)) continue;
    for (const element of namedBindings.elements) {
      const importedName = element.propertyName?.text || element.name.text;
      if (hookNames.has(importedName)) bindings.set(element.name.text, importedName);
    }
  }
  return bindings;
}

function collectHookConsumers(files, hookNames) {
  const consumers = new Map([...hookNames].map((hookName) => [hookName, []]));
  for (const filePath of files) {
    const kind = sourceKind(filePath);
    if (kind === "hook") continue;
    const text = fs.readFileSync(filePath, "utf8");
    const sourceFile = ts.createSourceFile(filePath, text, ts.ScriptTarget.Latest, true, scriptKind(filePath));
    const bindings = importedHookBindings(sourceFile, hookNames);
    if (!bindings.size) continue;
    const relativeFile = path.relative(repositoryRoot, filePath).split(path.sep).join("/");

    function visit(node) {
      if (ts.isCallExpression(node) && ts.isIdentifier(node.expression)) {
        const hookName = bindings.get(node.expression.text);
        if (hookName) {
          const localFunction = enclosingFunction(node, sourceFile);
          consumers.get(hookName).push({
            owner: localFunction?.name || ownerName(sourceFile, filePath),
            sourceKind: kind,
            file: relativeFile,
            line: lineNumber(sourceFile, node),
          });
        }
      }
      ts.forEachChild(node, visit);
    }
    visit(sourceFile);
  }
  for (const [hookName, surfaces] of consumers) {
    const deduplicated = [...new Map(surfaces.map((surface) => [
      `${surface.file}:${surface.line}:${surface.owner}`,
      surface,
    ])).values()].sort((left, right) => (
      left.file.localeCompare(right.file)
      || left.line - right.line
      || left.owner.localeCompare(right.owner)
    ));
    consumers.set(hookName, deduplicated);
  }
  return consumers;
}

const files = unique(sourceRoots.flatMap(listSourceFiles)).sort();
const extractedCalls = files.flatMap(extractFile);
const hookNames = new Set(
  extractedCalls.filter((call) => call.sourceKind === "hook").map((call) => call.owner),
);
const hookConsumers = collectHookConsumers(files, hookNames);
const calls = [...new Map(extractedCalls.map((call) => [
  `${call.file}:${call.line}:${call.method}:${call.path}`,
  {
    ...call,
    consumerSurfaces: call.sourceKind === "hook"
      ? hookConsumers.get(call.owner) || []
      : [{
          owner: call.owner,
          sourceKind: call.sourceKind,
          file: call.file,
          line: call.line,
        }],
  },
])).values()].sort((left, right) => (
  left.file.localeCompare(right.file)
  || left.line - right.line
  || left.method.localeCompare(right.method)
  || left.path.localeCompare(right.path)
));
process.stdout.write(`${JSON.stringify({ filesScanned: files.length, calls }, null, 2)}\n`);
