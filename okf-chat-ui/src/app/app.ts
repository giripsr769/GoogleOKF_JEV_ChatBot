import { Component } from '@angular/core';
import { ChatComponent } from './chat.component';
import { SidebarComponent } from './sidebar.component';

@Component({
  selector: 'app-root',
  imports: [SidebarComponent, ChatComponent],
  template: `
    <div class="layout">
      <app-sidebar />
      <main class="content"><app-chat /></main>
    </div>
  `,
  styles: `
    .layout { display: flex; height: 100vh; }
    .content { flex: 1; min-width: 0; height: 100%; }
  `,
})
export class App {}
