import { useStudioProjectStore } from '../projectStore';

describe('useStudioProjectStore', () => {
    beforeEach(() => {
        useStudioProjectStore.getState().reset();
    });

    it('keeps saved content separate from the working draft', () => {
        const state = useStudioProjectStore.getState();
        state.updateDraft('1', 'working code');

        let file = useStudioProjectStore.getState().files.find((candidate) => candidate.id === '1');
        expect(file).toMatchObject({ content: '', draft: 'working code', dirty: true });

        useStudioProjectStore.getState().saveFile('1');
        file = useStudioProjectStore.getState().files.find((candidate) => candidate.id === '1');
        expect(file).toMatchObject({ content: 'working code', draft: 'working code', dirty: false });
    });

    it('saveAll commits every draft', () => {
        const state = useStudioProjectStore.getState();
        state.updateDraft('1', 'strategy draft');
        state.updateDraft('2', '{"risk": 1}');
        useStudioProjectStore.getState().saveAll();

        expect(useStudioProjectStore.getState().files).toEqual(expect.arrayContaining([
            expect.objectContaining({ id: '1', content: 'strategy draft', dirty: false }),
            expect.objectContaining({ id: '2', content: '{"risk": 1}', dirty: false }),
        ]));
    });
});
