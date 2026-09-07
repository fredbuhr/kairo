export class KairoError extends Error {
  constructor(code, message, options = {}) {
    super(message, options);
    this.name = "KairoError";
    this.code = code;
  }
}
