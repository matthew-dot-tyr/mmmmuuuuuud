export class ApiError extends Error {
  constructor(status, detail) {
    super(detail || `Ошибка ${status}`);
    this.status = status;
    this.detail = detail;
  }
}
