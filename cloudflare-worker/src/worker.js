/**
 * CQR Dataset API — Cloudflare Worker
 *
 * Provides a REST API for querying the Contextual Query Rewrite dataset.
 * Handles long-running data processing tasks via Cloudflare Workers.
 *
 * Endpoints:
 *   GET  /                  — Health check and API info
 *   GET  /api/stats         — Dataset statistics
 *   GET  /api/splits        — List available splits (train/dev/test)
 *   GET  /api/data/:split   — Retrieve records from a split (supports ?limit=N&offset=M)
 *   GET  /api/search        — Search records (?q=query&split=train)
 *   GET  /api/checksums     — File integrity checksums
 *   POST /api/validate      — Trigger dataset validation task
 */

const SPLITS = ["train", "dev", "test"];
const SPLIT_FILES = {
  train: "cqr_kvret_train_public.json",
  dev: "cqr_kvret_dev_public.json",
  test: "cqr_kvret_test_public.json",
};

const CORS_HEADERS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type",
};

function jsonResponse(data, status = 200) {
  return new Response(JSON.stringify(data, null, 2), {
    status,
    headers: { "Content-Type": "application/json", ...CORS_HEADERS },
  });
}

async function fetchDatasetFile(env, split) {
  const filename = SPLIT_FILES[split];
  if (!filename) return null;

  // Try R2 cache first
  if (env.DATASET_CACHE) {
    const cached = await env.DATASET_CACHE.get(filename);
    if (cached) {
      return JSON.parse(await cached.text());
    }
  }

  // Fetch from GitHub (pinned to commit)
  const commitSha = env.COMMIT_SHA || "master";
  const url = `https://raw.githubusercontent.com/${env.DATASET_REPO}/${commitSha}/${filename}`;
  const resp = await fetch(url);
  if (!resp.ok) return null;

  const text = await resp.text();
  const data = JSON.parse(text);

  // Cache in R2
  if (env.DATASET_CACHE) {
    await env.DATASET_CACHE.put(filename, text);
  }

  return data;
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);

    if (request.method === "OPTIONS") {
      return new Response(null, { headers: CORS_HEADERS });
    }

    // Health check
    if (url.pathname === "/" || url.pathname === "/health") {
      return jsonResponse({
        service: "CQR Dataset API",
        status: "healthy",
        version: "1.0.0",
        commit: env.COMMIT_SHA || "unknown",
        endpoints: [
          "GET /api/stats",
          "GET /api/splits",
          "GET /api/data/:split",
          "GET /api/search?q=&split=",
          "GET /api/checksums",
          "POST /api/validate",
        ],
      });
    }

    // Dataset statistics
    if (url.pathname === "/api/stats") {
      const stats = {};
      for (const split of SPLITS) {
        const data = await fetchDatasetFile(env, split);
        stats[split] = {
          file: SPLIT_FILES[split],
          record_count: data ? (Array.isArray(data) ? data.length : Object.keys(data).length) : "unavailable",
        };
      }
      return jsonResponse({ dataset: "Contextual Query Rewrite (CQR)", splits: stats });
    }

    // List splits
    if (url.pathname === "/api/splits") {
      return jsonResponse({ splits: SPLITS, files: SPLIT_FILES });
    }

    // Get data from a split
    const dataMatch = url.pathname.match(/^\/api\/data\/(train|dev|test)$/);
    if (dataMatch) {
      const split = dataMatch[1];
      const limit = Math.min(parseInt(url.searchParams.get("limit") || "100", 10), 500);
      const offset = parseInt(url.searchParams.get("offset") || "0", 10);

      const data = await fetchDatasetFile(env, split);
      if (!data) return jsonResponse({ error: "Split not found" }, 404);

      const records = Array.isArray(data) ? data : Object.values(data);
      const slice = records.slice(offset, offset + limit);

      return jsonResponse({
        split,
        total: records.length,
        offset,
        limit,
        count: slice.length,
        records: slice,
      });
    }

    // Search
    if (url.pathname === "/api/search") {
      const query = (url.searchParams.get("q") || "").toLowerCase();
      const split = url.searchParams.get("split") || "train";
      const limit = Math.min(parseInt(url.searchParams.get("limit") || "20", 10), 100);

      if (!query) return jsonResponse({ error: "Missing ?q= parameter" }, 400);

      const data = await fetchDatasetFile(env, split);
      if (!data) return jsonResponse({ error: "Split not found" }, 404);

      const records = Array.isArray(data) ? data : Object.values(data);
      const results = [];

      for (const record of records) {
        if (results.length >= limit) break;
        const text = JSON.stringify(record).toLowerCase();
        if (text.includes(query)) {
          results.push(record);
        }
      }

      return jsonResponse({ query, split, count: results.length, results });
    }

    // Checksums
    if (url.pathname === "/api/checksums") {
      const commitSha = env.COMMIT_SHA || "master";
      const resp = await fetch(
        `https://raw.githubusercontent.com/${env.DATASET_REPO}/${commitSha}/checksums.json`
      );
      if (!resp.ok) return jsonResponse({ error: "Checksums not available" }, 404);
      const checksums = await resp.json();
      return jsonResponse(checksums);
    }

    // Validate (long-running task)
    if (url.pathname === "/api/validate" && request.method === "POST") {
      const validationResults = {};
      for (const split of SPLITS) {
        const data = await fetchDatasetFile(env, split);
        if (!data) {
          validationResults[split] = { status: "error", message: "File not found" };
          continue;
        }
        const records = Array.isArray(data) ? data : Object.values(data);
        let reformulationCount = 0;
        for (const record of records) {
          if (record.reformulation) reformulationCount++;
        }
        validationResults[split] = {
          status: "pass",
          record_count: records.length,
          records_with_reformulations: reformulationCount,
        };
      }
      return jsonResponse({ validation: "complete", results: validationResults });
    }

    return jsonResponse({ error: "Not Found" }, 404);
  },

  // Scheduled task: refresh R2 cache
  async scheduled(event, env, ctx) {
    for (const split of SPLITS) {
      const filename = SPLIT_FILES[split];
      const commitSha = env.COMMIT_SHA || "master";
      const url = `https://raw.githubusercontent.com/${env.DATASET_REPO}/${commitSha}/${filename}`;
      const resp = await fetch(url);
      if (resp.ok && env.DATASET_CACHE) {
        const text = await resp.text();
        await env.DATASET_CACHE.put(filename, text);
      }
    }
  },
};
