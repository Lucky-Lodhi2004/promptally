#!/usr/bin/env node

/**
 * Ingestion Pipeline for Awesome ChatGPT Prompts (English canonical repository)
 *
 * Merges with existing prompts and saves as:
 * /home/lucky/repos/Promptally/data/extracted/persona_prompts.json
 */

const fs = require('fs');
const path = require('path');

const CSV_PATH = '/tmp/awesome_prompts.csv';
const OLD_FABRIC_FILE = path.join(__dirname, '../../data/extracted/fabric_prompts.json');
const OUTPUT_FILE = path.join(__dirname, '../../data/extracted/persona_prompts.json');

// RFC 4180 CSV parser
function parseCSV(text) {
  const rows = [];
  let currentRow = [];
  let currentVal = '';
  let insideQuotes = false;

  for (let i = 0; i < text.length; i++) {
    const char = text[i];
    const nextChar = text[i + 1];

    if (char === '"') {
      if (insideQuotes && nextChar === '"') {
        currentVal += '"';
        i++;
      } else {
        insideQuotes = !insideQuotes;
      }
    } else if (char === ',' && !insideQuotes) {
      currentRow.push(currentVal);
      currentVal = '';
    } else if ((char === '\r' || char === '\n') && !insideQuotes) {
      if (char === '\r' && nextChar === '\n') i++;
      currentRow.push(currentVal);
      if (currentRow.some(cell => cell.trim().length > 0)) {
        rows.push(currentRow);
      }
      currentRow = [];
      currentVal = '';
    } else {
      currentVal += char;
    }
  }
  if (currentVal || currentRow.length > 0) {
    currentRow.push(currentVal);
    rows.push(currentRow);
  }
  return rows;
}

function classifyAwesomePrompt(act, prompt, forDevs) {
  const a = act.toLowerCase();
  const p = prompt.toLowerCase();

  if (
    forDevs === 'TRUE' ||
    a.includes('developer') ||
    a.includes('terminal') ||
    a.includes('console') ||
    a.includes('coder') ||
    a.includes('programming') ||
    a.includes('sql') ||
    a.includes('regex') ||
    a.includes('python') ||
    a.includes('javascript') ||
    a.includes('solidity') ||
    a.includes('git')
  ) {
    return 'coding_prompt';
  }

  if (
    a.includes('tutor') ||
    a.includes('teacher') ||
    a.includes('interviewer') ||
    a.includes('coach') ||
    a.includes('guide') ||
    a.includes('doctor') ||
    a.includes('character') ||
    a.includes('philosopher') ||
    a.includes('historian') ||
    a.includes('critic') ||
    a.includes('friend') ||
    a.includes('debater') ||
    a.includes('counselor') ||
    a.includes('examiner')
  ) {
    return 'roleplay_prompt';
  }

  return 'personalization_prompt';
}

function generateTitle(act) {
  const cleanAct = act.trim();
  const lower = cleanAct.toLowerCase();
  if (lower.startsWith('act as') || lower.startsWith('act like')) {
    return `Prompt to ${cleanAct}`;
  }
  return `Prompt to Turn ChatGPT into an ${cleanAct}`;
}

function extractTags(act, prompt, promptType) {
  const tags = new Set(['awesome-chatgpt-prompts', 'chatgpt-persona']);
  const combined = (act + ' ' + prompt).toLowerCase();

  if (promptType === 'coding_prompt') tags.add('coding');
  if (promptType === 'roleplay_prompt') tags.add('roleplay');
  if (promptType === 'personalization_prompt') tags.add('personalization');

  if (combined.includes('tutor') || combined.includes('teacher')) tags.add('education');
  if (combined.includes('interview')) tags.add('interview-prep');
  if (combined.includes('writer') || combined.includes('storyteller')) tags.add('creative-writing');
  if (combined.includes('translator')) tags.add('translation');

  return Array.from(tags);
}

function run() {
  // 1. Load existing fabric prompts
  let existing = [];
  if (fs.existsSync(OUTPUT_FILE)) {
    existing = JSON.parse(fs.readFileSync(OUTPUT_FILE, 'utf8'));
  } else if (fs.existsSync(OLD_FABRIC_FILE)) {
    existing = JSON.parse(fs.readFileSync(OLD_FABRIC_FILE, 'utf8'));
  }

  console.log(`Starting with ${existing.length} existing prompts...`);

  // Build a set of exact prompts to avoid duplicates
  const existingPromptSet = new Set(existing.map(p => p.exact_prompt.trim()));

  // 2. Parse awesome-chatgpt-prompts
  const csvContent = fs.readFileSync(CSV_PATH, 'utf8');
  const rows = parseCSV(csvContent);

  const header = rows[0];
  const actIdx = header.indexOf('act');
  const promptIdx = header.indexOf('prompt');
  const forDevsIdx = header.indexOf('for_devs');

  let addedCount = 0;
  let skippedDuplicates = 0;

  for (let i = 1; i < rows.length; i++) {
    const row = rows[i];
    const act = (row[actIdx] || '').trim();
    const prompt = (row[promptIdx] || '').trim();
    const forDevs = (row[forDevsIdx] || '').trim().toUpperCase();

    if (!act || !prompt || prompt.length < 15) continue;

    if (existingPromptSet.has(prompt)) {
      skippedDuplicates++;
      continue;
    }

    const promptType = classifyAwesomePrompt(act, prompt, forDevs);
    const title = generateTitle(act);
    const tags = extractTags(act, prompt, promptType);
    const slug = act.toLowerCase().replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '');

    existing.push({
      prompt_title: title,
      exact_prompt: prompt,
      prompt_type: promptType,
      source_slug: slug,
      tags: tags,
      source_repo: 'https://github.com/f/awesome-chatgpt-prompts',
      license: 'CC0-1.0'
    });

    existingPromptSet.add(prompt);
    addedCount++;
  }

  // 3. Write to persona_prompts.json
  fs.writeFileSync(OUTPUT_FILE, JSON.stringify(existing, null, 2), 'utf8');

  // Remove old fabric_prompts.json if present
  if (fs.existsSync(OLD_FABRIC_FILE)) {
    fs.unlinkSync(OLD_FABRIC_FILE);
  }

  console.log(`Successfully added ${addedCount} prompts from awesome-chatgpt-prompts.`);
  console.log(`Skipped ${skippedDuplicates} duplicate prompts.`);
  console.log(`Total prompts in ${OUTPUT_FILE}: ${existing.length}`);

  // Summary by prompt_type
  const typeCounts = existing.reduce((acc, p) => {
    acc[p.prompt_type] = (acc[p.prompt_type] || 0) + 1;
    return acc;
  }, {});
  console.log('Final breakdown by prompt_type:', JSON.stringify(typeCounts, null, 2));
}

run();

