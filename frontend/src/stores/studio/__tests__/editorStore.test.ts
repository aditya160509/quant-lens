import { STRATEGIES } from '@/components/studio/constants';
import { defaultEditorState, useStudioEditorStore } from '../editorStore';

describe('useStudioEditorStore', () => {
    beforeEach(() => {
        jest.mocked(window.localStorage.getItem).mockReset();
        jest.mocked(window.localStorage.setItem).mockReset();
        jest.mocked(window.localStorage.removeItem).mockReset();
        useStudioEditorStore.getState().resetEditor();
    });

    it('applies a known strategy to both editor drafts', () => {
        useStudioEditorStore.getState().applyStrategy('rsi');

        const state = useStudioEditorStore.getState();
        expect(state.selectedStrategy).toBe('rsi');
        expect(state.codeA).toBe(STRATEGIES.rsi.code);
        expect(state.codeB).toBe(STRATEGIES.rsi.code);
        expect(window.localStorage.setItem).toHaveBeenCalledWith(
            'sovereign_studio_code_a',
            STRATEGIES.rsi.code,
        );
        expect(window.localStorage.setItem).toHaveBeenCalledWith(
            'sovereign_studio_code_b',
            STRATEGIES.rsi.code,
        );
    });

    it('supports React-style functional updates', () => {
        const state = useStudioEditorStore.getState();
        state.setCodeA((current: string) => `${current}\n# edited`);
        state.setVsModeActive((current: boolean) => !current);

        expect(useStudioEditorStore.getState().codeA).toBe(`${defaultEditorState.codeA}\n# edited`);
        expect(useStudioEditorStore.getState().vsModeActive).toBe(true);
    });

    it('hydrates drafts from the legacy storage keys', () => {
        jest.mocked(window.localStorage.getItem).mockImplementation((key) => (
            key === 'sovereign_studio_code_a' ? 'alpha draft' : 'beta draft'
        ));

        useStudioEditorStore.getState().hydrateDrafts();

        expect(useStudioEditorStore.getState().codeA).toBe('alpha draft');
        expect(useStudioEditorStore.getState().codeB).toBe('beta draft');
    });
});
