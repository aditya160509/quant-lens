export type Merge = { left: number; right: number; distance: number; count?: number };

/** Linkage children must precede their parent. Reject malformed trees rather than recursing forever. */
export function validLinkage(merges: Merge[], n: number): boolean {
  if (n < 2 || merges.length !== n - 1) return false;
  const used = new Set<number>();
  return merges.every((m, i) => {
    const children = [m.left, m.right];
    if (!Number.isFinite(m.distance) || m.distance < 0 || children.some((c) => !Number.isInteger(c) || c < 0 || c >= n + i || used.has(c)) || m.left === m.right) return false;
    children.forEach((c) => used.add(c));
    return true;
  });
}

export function leafOrder(merges: Merge[], n: number): number[] {
  if (!validLinkage(merges, n)) return Array.from({ length: n }, (_, i) => i);
  const result: number[] = [], pending = [n + merges.length - 1];
  while (pending.length) {
    const id = pending.pop()!;
    if (id < n) result.push(id);
    else { const m = merges[id - n]; pending.push(m.right, m.left); }
  }
  return result;
}

/** Every subtree below the cut has one cluster id, including singleton leaves. */
export function clusterIds(merges: Merge[], n: number, cut: number): number[] {
  const ids = Array.from({ length: n }, (_, i) => i);
  if (!validLinkage(merges, n)) return ids;
  let next = 0;
  const pending = [n + merges.length - 1];
  while (pending.length) {
    const root = pending.pop()!;
    if (root >= n && merges[root - n].distance > cut) {
      const m = merges[root - n]; pending.push(m.right, m.left); continue;
    }
    const members = [root];
    while (members.length) {
      const id = members.pop()!;
      if (id < n) ids[id] = next;
      else { const m = merges[id - n]; members.push(m.right, m.left); }
    }
    next++;
  }
  return ids;
}
