#!/usr/bin/env node

/**
 * Ingestion Pipeline for Fabric Patterns (danielmiessler/fabric)
 *
 * Extracts prompts from /tmp/fabric/data/patterns/* /system.md
 * and formats them into a clean JSON output with:
 * - prompt_title: Human-readable, intent-driven SEO title
 * - exact_prompt: The verbatim markdown prompt system definition
 * - prompt_type: Accurately classified (e.g. personalization_prompt, coding_prompt, roleplay_prompt, etc.)
 * - source_slug: Original folder pattern name
 * - tags: Descriptive tags for filtering
 */

const fs = require('fs');
const path = require('path');

const PATTERNS_DIR = '/tmp/fabric/data/patterns';
const OUTPUT_FILE = path.join(__dirname, '../../data/extracted/fabric_prompts.json');

// Map pattern names / keywords to exact prompt types
function classifyPromptType(slug, content) {
  const s = slug.toLowerCase();
  const c = content.toLowerCase();

  // Coding prompts
  if (
    s.includes('code') ||
    s.includes('git') ||
    s.includes('sql') ||
    s.includes('regex') ||
    s.includes('api') ||
    s.includes('docker') ||
    s.includes('latex') ||
    s.includes('html') ||
    s.includes('css') ||
    s.includes('threat_model') ||
    s.includes('malware') ||
    s.includes('vulnerability') ||
    s.includes('security') ||
    c.includes('you are a senior software') ||
    c.includes('programming language') ||
    c.includes('clean code')
  ) {
    return 'coding_prompt';
  }

  // Roleplay / Character persona prompts
  if (
    s.includes('dialog') ||
    s.includes('debate') ||
    s.includes('interview') ||
    s.includes('coach') ||
    s.includes('tutor') ||
    s.includes('mentor') ||
    s.includes('philosopher') ||
    s.includes('stoic') ||
    s.includes('expert')
  ) {
    return 'roleplay_prompt';
  }

  // Personalization / Persona / Mindset / Writing tone prompts
  if (
    s.includes('persona') ||
    s.includes('personality') ||
    s.includes('habit') ||
    s.includes('human') ||
    s.includes('voice') ||
    s.includes('tone') ||
    s.includes('pinker') ||
    s.includes('prose') ||
    s.includes('essay') ||
    s.includes('write') ||
    s.includes('wisdom') ||
    s.includes('advice') ||
    s.includes('life') ||
    s.includes('rate') ||
    s.includes('improve') ||
    s.includes('explain') ||
    s.includes('summarize') ||
    s.includes('analyze')
  ) {
    return 'personalization_prompt';
  }

  return 'personalization_prompt';
}

// Convert a slug like "extract_wisdom" into an intent-driven heading
function generatePromptTitle(slug, content) {
  // Check if first line of content has an identity/purpose title
  const match = content.match(/#\s*IDENTITY\s*(?:and|&)\s*PURPOSE\s*\n+([^\n#]+)/i);
  let summary = '';
  if (match && match[1]) {
    const rawSentence = match[1].trim();
    if (rawSentence.length > 10 && rawSentence.length < 120) {
      summary = rawSentence.replace(/^You (?:are|act as|serve as|extract|analyze|evaluate)\s+/i, '');
    }
  }

  // Turn slug words into title words
  const words = slug.split('_').map(w => w.charAt(0).toUpperCase() + w.slice(1));
  const readable = words.join(' ');

  // Generate strong intent title
  return `Prompt to ${readable.toLowerCase().startsWith('prompt to') ? readable.slice(10) : readable}`;
}

// Extract tags based on slug and content
function extractTags(slug, content) {
  const tags = new Set(['fabric', 'system-prompt', 'production-grade']);
  const s = slug.toLowerCase();

  if (s.includes('code') || s.includes('security') || s.includes('threat')) tags.add('coding');
  if (s.includes('analyze')) tags.add('analysis');
  if (s.includes('extract')) tags.add('extraction');
  if (s.includes('write') || s.includes('prose') || s.includes('essay')) tags.add('writing');
  if (s.includes('summarize')) tags.add('summarization');
  if (s.includes('wisdom') || s.includes('philosophy') || s.includes('habit')) tags.add('mindset');
  if (s.includes('debate') || s.includes('interview')) tags.add('roleplay');

  return Array.from(tags);
}

function runIngestion() {
  if (!fs.existsSync(PATTERNS_DIR)) {
    console.error(`Error: Patterns directory not found at ${PATTERNS_DIR}`);
    process.exit(1);
  }

  const entries = fs.readdirSync(PATTERNS_DIR, { withFileTypes: true });
  const results = [];

  for (const entry of entries) {
    if (!entry.isDirectory()) continue;

    const patternSlug = entry.name;
    const systemMdPath = path.join(PATTERNS_DIR, patternSlug, 'system.md');

    if (!fs.existsSync(systemMdPath)) {
      continue;
    }

    const rawPrompt = fs.readFileSync(systemMdPath, 'utf-8').trim();
    if (!rawPrompt) continue;

    const promptType = classifyPromptType(patternSlug, rawPrompt);
    const promptTitle = generatePromptTitle(patternSlug, rawPrompt);
    const tags = extractTags(patternSlug, rawPrompt);

    results.push({
      prompt_title: promptTitle,
      exact_prompt: rawPrompt,
      prompt_type: promptType,
      source_slug: patternSlug,
      tags: tags,
      source_repo: "https://github.com/danielmiessler/fabric",
      license: "MIT"
    });
  }

  fs.mkdirSync(path.dirname(OUTPUT_FILE), { recursive: true });
  fs.writeFileSync(OUTPUT_FILE, JSON.stringify(results, null, 2), 'utf-8');

  console.log(`Successfully ingested ${results.length} prompts from danielmiessler/fabric into ${OUTPUT_FILE}`);

  // Print a summary of counts by type
  const typeCounts = results.reduce((acc, p) => {
    acc[p.prompt_type] = (acc[p.prompt_type] || 0) + 1;
    return acc;
  }, {});

  console.log('Breakdown by prompt_type:', JSON.stringify(typeCounts, null, 2));
}

runIngestion();

