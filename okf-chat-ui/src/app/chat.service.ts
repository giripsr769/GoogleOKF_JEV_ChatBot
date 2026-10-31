import { HttpClient } from '@angular/common/http';
import { Injectable, inject } from '@angular/core';
import { Observable, timeout } from 'rxjs';
import { environment } from './environment';

export interface QueryResponse {
  question: string;
  sql: string;
  tables_used: string[];
  columns: string[];
  rows: Record<string, unknown>[];
  row_count: number;
  risk_score: number;
  timings_ms: Record<string, number>;
  /** natural-language reply; absent in chats saved before this existed */
  answer?: string;
  /** false = show only the reply (the user did not ask for a table); absent = legacy, show it */
  show_table?: boolean;
}

export interface Health {
  status: string;
  tables_indexed: number;
}

@Injectable({ providedIn: 'root' })
export class ChatService {
  private http = inject(HttpClient);

  ask(question: string): Observable<QueryResponse> {
    return this.http
      .post<QueryResponse>(`${environment.apiUrl}/api/text-to-sql`, { question })
      .pipe(timeout(environment.requestTimeoutMs)); // unsubscribing on timeout also cancels the HTTP request
  }

  health(): Observable<Health> {
    return this.http.get<Health>(`${environment.apiUrl}/health`);
  }
}
