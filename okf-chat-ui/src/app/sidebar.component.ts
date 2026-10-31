import { Component, inject, signal } from '@angular/core';
import { ChatStore } from './chat-store.service';

const MOBILE_MAX = 800;

@Component({
  selector: 'app-sidebar',
  templateUrl: './sidebar.component.html',
  styleUrl: './sidebar.component.css',
})
export class SidebarComponent {
  protected store = inject(ChatStore);
  protected confirmClear = signal(false);
  private confirmTimer?: ReturnType<typeof setTimeout>;

  newChat() {
    this.store.newChat();
    this.closeIfMobile();
  }

  open(id: string) {
    this.store.select(id);
    this.closeIfMobile();
  }

  /** Two-step clear: first click arms it, second click within 3s confirms (no browser dialog). */
  clearAll() {
    if (!this.confirmClear()) {
      this.confirmClear.set(true);
      this.confirmTimer = setTimeout(() => this.confirmClear.set(false), 3000);
      return;
    }
    clearTimeout(this.confirmTimer);
    this.confirmClear.set(false);
    this.store.clearAll();
  }

  onSqlToggle(event: Event) {
    this.store.setShowSql((event.target as HTMLInputElement).checked);
  }

  private closeIfMobile() {
    if (window.innerWidth <= MOBILE_MAX && this.store.sidebarOpen()) this.store.toggleSidebar();
  }
}
