import { randomUUID } from "node:crypto";

export function createId(prefix) {
  return `${prefix}_${randomUUID()}`;
}

export function slugify(value) {
  const slug = String(value ?? "")
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");

  if (!slug) {
    throw new TypeError("A non-empty slug-compatible value is required.");
  }
  return slug;
}

export function assertSafeId(value, label = "id") {
  if (!/^[a-z][a-z0-9_-]*_[0-9a-f-]{36}$/i.test(value)) {
    throw new TypeError(`Invalid ${label}.`);
  }
  return value;
}
