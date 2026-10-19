// The app's stage. Milestone 1 only uses 'camera'; the scan, solve and guided
// stages arrive in later milestones.

export type Phase = 'starting' | 'camera' | 'scan' | 'review' | 'guided' | 'undo' | 'solved';

export class AppState {
  phase: Phase = 'starting';
  /** True while the user is off track (red hand mesh, amber warning). */
  error = false;
  private listeners: ((s: AppState) => void)[] = [];

  set(phase: Phase): void {
    this.phase = phase;
    this.listeners.forEach((f) => f(this));
  }

  subscribe(f: (s: AppState) => void): void {
    this.listeners.push(f);
  }
}
