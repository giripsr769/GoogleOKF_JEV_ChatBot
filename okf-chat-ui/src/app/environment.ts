export const environment = {
  apiUrl: 'http://localhost:8000',
  /** UI backstop: just above the backend's 30s budget, so the backend's clean 504 normally arrives first */
  requestTimeoutMs: 40000,
};
