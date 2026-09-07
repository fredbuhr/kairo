const FRONTMATTER_DELIMITER = "---";

export function serializeMarkdown(metadata, body) {
  const lines = Object.entries(metadata).map(([key, value]) => {
    if (!/^[a-z][a-z0-9_]*$/i.test(key)) {
      throw new TypeError(`Invalid front matter key: ${key}`);
    }
    return `${key}: ${JSON.stringify(value)}`;
  });

  return [FRONTMATTER_DELIMITER, ...lines, FRONTMATTER_DELIMITER, "", body.trim(), ""].join("\n");
}

export function parseMarkdown(input) {
  const text = String(input);
  const lines = text.split(/\r?\n/);
  if (lines[0] !== FRONTMATTER_DELIMITER) {
    throw new TypeError("Markdown document is missing front matter.");
  }

  const end = lines.indexOf(FRONTMATTER_DELIMITER, 1);
  if (end === -1) {
    throw new TypeError("Markdown front matter is not terminated.");
  }

  const metadata = {};
  for (const line of lines.slice(1, end)) {
    if (!line.trim()) continue;
    const separator = line.indexOf(":");
    if (separator <= 0) throw new TypeError(`Invalid front matter line: ${line}`);
    const key = line.slice(0, separator).trim();
    const raw = line.slice(separator + 1).trim();
    if (!/^[a-z][a-z0-9_]*$/i.test(key)) throw new TypeError(`Invalid front matter key: ${key}`);
    try {
      metadata[key] = JSON.parse(raw);
    } catch {
      metadata[key] = raw;
    }
  }

  return {
    metadata,
    body: lines.slice(end + 1).join("\n").trim(),
  };
}
