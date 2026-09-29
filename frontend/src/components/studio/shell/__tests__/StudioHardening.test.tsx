import { fireEvent, render, screen } from '@testing-library/react';
import React from 'react';
import StudioConfirm from '../StudioConfirm';
import { studioFlagSnapshot } from '../studioFeatureFlags';
import { useUnsavedGuard } from '../useUnsavedGuard';

describe('P15 Studio shell hardening', () => {
  it('confirms destructive actions through an labelled alertdialog', () => {
    const onConfirm = jest.fn();
    const onCancel = jest.fn();
    render(
      <StudioConfirm
        open
        title="Delete version"
        body="This removes the saved portfolio version."
        confirmLabel="Delete"
        onConfirm={onConfirm}
        onCancel={onCancel}
      />,
    );

    const dialog = screen.getByRole('alertdialog', { name: 'Delete version' });
    expect(dialog).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: /delete/i }));
    expect(onConfirm).toHaveBeenCalledTimes(1);

    fireEvent.keyDown(document, { key: 'Escape' });
    expect(onCancel).toHaveBeenCalled();
  });

  it('guards unsaved work with beforeunload only while dirty', () => {
    const calls: Array<() => void> = [];
    const Probe = ({ dirty }: { dirty: boolean }) => {
      useUnsavedGuard(dirty);
      return null;
    };
    const addSpy = jest.spyOn(window, 'addEventListener');
    const removeSpy = jest.spyOn(window, 'removeEventListener');

    const { rerender, unmount } = render(<Probe dirty={false} />);
    expect(addSpy).not.toHaveBeenCalledWith('beforeunload', expect.any(Function));

    rerender(<Probe dirty />);
    const handler = addSpy.mock.calls.find(([type]) => type === 'beforeunload')?.[1] as EventListener;
    expect(handler).toBeDefined();
    const event = new Event('beforeunload', { cancelable: true });
    handler(event);
    expect((event as BeforeUnloadEvent).returnValue).not.toBeUndefined();

    unmount();
    expect(removeSpy).toHaveBeenCalledWith('beforeunload', handler);
    addSpy.mockRestore();
    removeSpy.mockRestore();
    expect(calls).toHaveLength(0);
  });

  it('keeps risky renderer/worker paths off by default', () => {
    expect(studioFlagSnapshot()).toEqual({
      STUDIO_RENDERER_WEBGL: false,
      STUDIO_WORKER_EXTERNAL: false,
      STUDIO_GPU_ENABLED: false,
      STUDIO_PARQUET_FAST_SCAN: false,
    });
  });
});
