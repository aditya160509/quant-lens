/**
 * Alert Notifier
 * Browser notification integration with sound support
 */

import type { Alert, AlertTriggerEvent } from './alertTypes';

// =============================================================================
// NOTIFICATION MANAGER
// =============================================================================

class AlertNotifier {
    private static instance: AlertNotifier;
    private permissionGranted: boolean = false;
    private audioContext: AudioContext | null = null;
    private notificationQueue: AlertTriggerEvent[] = [];

    private constructor() {
        this.initializePermission();
    }

    static getInstance(): AlertNotifier {
        if (!AlertNotifier.instance) {
            AlertNotifier.instance = new AlertNotifier();
        }
        return AlertNotifier.instance;
    }

    // ==========================================================================
    // PERMISSION MANAGEMENT
    // ==========================================================================

    async initializePermission(): Promise<boolean> {
        if (typeof window === 'undefined' || !('Notification' in window)) {
            console.warn('Browser notifications not supported');
            return false;
        }

        if (Notification.permission === 'granted') {
            this.permissionGranted = true;
            return true;
        }

        if (Notification.permission !== 'denied') {
            try {
                const permission = await Notification.requestPermission();
                this.permissionGranted = permission === 'granted';
                return this.permissionGranted;
            } catch (error) {
                console.error('Failed to request notification permission:', error);
                return false;
            }
        }

        return false;
    }

    async requestPermission(): Promise<boolean> {
        return this.initializePermission();
    }

    getPermissionStatus(): NotificationPermission | 'unsupported' {
        if (typeof window === 'undefined' || !('Notification' in window)) {
            return 'unsupported';
        }
        return Notification.permission;
    }

    // ==========================================================================
    // NOTIFICATION SENDING
    // ==========================================================================

    async notify(alert: Alert, event: AlertTriggerEvent): Promise<void> {
        const { notification } = alert;

        // Browser notification
        if (notification.method === 'browser' || notification.method === 'both') {
            await this.showBrowserNotification(alert, event);
        }

        // Sound notification
        if (notification.method === 'sound' || notification.method === 'both') {
            await this.playSound(notification.soundFile);
        }
    }

    private async showBrowserNotification(
        alert: Alert, 
        event: AlertTriggerEvent
    ): Promise<Notification | null> {
        if (!this.permissionGranted) {
            const granted = await this.requestPermission();
            if (!granted) {
                console.warn('Notification permission not granted');
                return null;
            }
        }

        try {
            const notification = new Notification(`🔔 ${alert.symbol} Alert`, {
                body: event.message,
                icon: '/favicon.ico',
                badge: '/favicon.ico',
                tag: alert.id, // Prevents duplicate notifications
                requireInteraction: !alert.notification.autoExpire,
                silent: alert.notification.method === 'browser', // No sound if only browser
                data: {
                    alertId: alert.id,
                    symbol: alert.symbol,
                    price: event.price,
                    timestamp: event.timestamp,
                },
            });

            // Auto-close after specified time
            if (alert.notification.autoExpire && alert.notification.expireAfterMs) {
                setTimeout(() => {
                    notification.close();
                }, alert.notification.expireAfterMs);
            }

            // Click handler
            notification.onclick = () => {
                window.focus();
                notification.close();
                // Dispatch custom event for UI to handle
                window.dispatchEvent(new CustomEvent('alert-notification-click', {
                    detail: { alertId: alert.id }
                }));
            };

            return notification;
        } catch (error) {
            console.error('Failed to show notification:', error);
            return null;
        }
    }

    // ==========================================================================
    // SOUND MANAGEMENT
    // ==========================================================================

    private async playSound(soundFile?: string): Promise<void> {
        try {
            // Initialize AudioContext on first use (must be after user interaction)
            if (!this.audioContext) {
                this.audioContext = new (window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext)();
            }

            // Use a simple oscillator beep if no custom sound file
            if (!soundFile) {
                await this.playBeep();
                return;
            }

            // Load and play custom sound
            const response = await fetch(soundFile);
            const arrayBuffer = await response.arrayBuffer();
            const audioBuffer = await this.audioContext.decodeAudioData(arrayBuffer);
            
            const source = this.audioContext.createBufferSource();
            source.buffer = audioBuffer;
            source.connect(this.audioContext.destination);
            source.start(0);
        } catch (error) {
            console.error('Failed to play sound:', error);
            // Fallback to beep
            await this.playBeep();
        }
    }

    private async playBeep(): Promise<void> {
        if (!this.audioContext) {
            this.audioContext = new (window.AudioContext || (window as unknown as { webkitAudioContext: typeof AudioContext }).webkitAudioContext)();
        }

        const oscillator = this.audioContext.createOscillator();
        const gainNode = this.audioContext.createGain();

        oscillator.connect(gainNode);
        gainNode.connect(this.audioContext.destination);

        // Configure beep
        oscillator.frequency.value = 880; // A5 note
        oscillator.type = 'sine';
        
        // Fade out
        gainNode.gain.setValueAtTime(0.3, this.audioContext.currentTime);
        gainNode.gain.exponentialRampToValueAtTime(0.01, this.audioContext.currentTime + 0.3);

        oscillator.start(this.audioContext.currentTime);
        oscillator.stop(this.audioContext.currentTime + 0.3);
    }

    // ==========================================================================
    // POPUP MANAGEMENT (for in-app popups)
    // ==========================================================================

    private popupCallbacks: Set<(event: AlertTriggerEvent, alert: Alert) => void> = new Set();

    registerPopupCallback(callback: (event: AlertTriggerEvent, alert: Alert) => void): () => void {
        this.popupCallbacks.add(callback);
        return () => this.popupCallbacks.delete(callback);
    }

    showPopup(alert: Alert, event: AlertTriggerEvent): void {
        if (alert.notification.showPopup) {
            this.popupCallbacks.forEach(callback => callback(event, alert));
        }
    }

    // ==========================================================================
    // FULL NOTIFICATION FLOW
    // ==========================================================================

    async triggerAlert(alert: Alert, event: AlertTriggerEvent): Promise<void> {
        // Show browser notification
        await this.notify(alert, event);

        // Show in-app popup
        this.showPopup(alert, event);

        // Log to console for debugging
        console.log(`[Alert Triggered] ${alert.symbol}: ${event.message}`);
    }
}

// Export singleton instance
export const alertNotifier = AlertNotifier.getInstance();

// Export convenience functions
export async function requestNotificationPermission(): Promise<boolean> {
    return alertNotifier.requestPermission();
}

export function getNotificationPermission(): NotificationPermission | 'unsupported' {
    return alertNotifier.getPermissionStatus();
}

export async function triggerAlertNotification(
    alert: Alert, 
    event: AlertTriggerEvent
): Promise<void> {
    return alertNotifier.triggerAlert(alert, event);
}

export function registerAlertPopupHandler(
    callback: (event: AlertTriggerEvent, alert: Alert) => void
): () => void {
    return alertNotifier.registerPopupCallback(callback);
}
