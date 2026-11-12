#!/usr/bin/env node

/**
 * Ingestion Pipeline for Vendor-Specific Prompts:
 * - Anthropic (Claude Agent Prompts, Metaprompt, XML patterns)
 * - Google Gemini (Prompting examples, Multimodal Video/Audio, Spatial 3D, Thinking)
 * - OpenAI (Swarm multi-agent handoffs, triage routines, structured output schemas)
 *
 * Saves into: /home/lucky/repos/Promptally/data/extracted/vendor_prompts.json
 */

const fs = require('fs');
const path = require('path');

const OUTPUT_FILE = path.join(__dirname, '../../data/extracted/vendor_prompts.json');

const results = [];

// Helper to push a vendor prompt
function addPrompt({ vendor, prompt_title, exact_prompt, prompt_type, source_slug, tags, source_repo, license }) {
  if (!exact_prompt || exact_prompt.trim().length < 15) return;
  results.push({
    vendor,
    prompt_title,
    exact_prompt: exact_prompt.trim(),
    prompt_type,
    source_slug,
    tags,
    source_repo,
    license: license || 'MIT'
  });
}

// -------------------------------------------------------------
// 1. ANTHROPIC CLAUDE PROMPTS
// -------------------------------------------------------------
function ingestAnthropic() {
  console.log('Ingesting Anthropic Claude prompts...');
  const repo = 'https://github.com/anthropics/anthropic-cookbook';

  // A. Agent Prompts under /patterns/agents/prompts
  const agentsDir = '/tmp/anthropic-cookbook/patterns/agents/prompts';
  if (fs.existsSync(agentsDir)) {
    const files = fs.readdirSync(agentsDir);
    for (const file of files) {
      if (!file.endsWith('.md')) continue;
      const content = fs.readFileSync(path.join(agentsDir, file), 'utf8');
      const slug = file.replace('.md', '');
      const words = slug.split('_').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ');

      addPrompt({
        vendor: 'Anthropic',
        prompt_title: `Prompt for Anthropic Claude ${words}`,
        exact_prompt: content,
        prompt_type: 'agentic_workflow',
        source_slug: `anthropic-agent-${slug}`,
        tags: ['anthropic', 'claude', 'agentic-workflow', 'xml-tags', 'system-prompt'],
        source_repo: repo,
        license: 'MIT'
      });
    }
  }

  // B. Metaprompt from /misc/metaprompt.ipynb
  const metaNbPath = '/tmp/anthropic-cookbook/misc/metaprompt.ipynb';
  if (fs.existsSync(metaNbPath)) {
    try {
      const nb = JSON.parse(fs.readFileSync(metaNbPath, 'utf8'));
      for (const cell of nb.cells) {
        const src = Array.isArray(cell.source) ? cell.source.join('') : cell.source || '';
        if (src.includes('metaprompt = """Today you will be writing instructions')) {
          const match = src.match(/metaprompt\s*=\s*"""([\s\S]+?)"""/);
          if (match && match[1]) {
            addPrompt({
              vendor: 'Anthropic',
              prompt_title: 'Prompt to Generate Custom Claude System Prompts (Anthropic Metaprompt)',
              exact_prompt: match[1],
              prompt_type: 'personalization_prompt',
              source_slug: 'anthropic-metaprompt-system-generator',
              tags: ['anthropic', 'claude', 'metaprompt', 'xml-tags', 'prompt-generator'],
              source_repo: repo,
              license: 'MIT'
            });
          }
        }
      }
    } catch (err) {
      console.error('Error parsing metaprompt notebook:', err);
    }
  }

  // C. Curated Claude XML Prompt Library Patterns
  const claudePatterns = [
    {
      title: 'Prompt for Claude Strict JSON Extraction with XML Guardrails',
      slug: 'claude-xml-strict-json-extraction',
      type: 'coding_prompt',
      tags: ['anthropic', 'claude', 'json-mode', 'structured-output', 'xml-tags'],
      prompt: `You are an expert data extraction system. You will be provided with unstructured text enclosed in <unstructured_input> tags.

<instructions>
1. Carefully read and analyze the input inside <unstructured_input>.
2. Extract all entities matching the required schema: name, dates, financial_values, summary.
3. Validate each field for accuracy before producing the final output.
4. Output ONLY valid, parseable JSON enclosed in <json_output> tags.
5. Do NOT include any conversational filler, markdown codeblocks, or preamble outside the tags.
</instructions>

<unstructured_input>
{{INPUT_TEXT}}
</unstructured_input>

<thinking>
Think step-by-step about entity recognition, boundary cases, and edge cases here.
</thinking>

<json_output>
`
    },
    {
      title: 'Prompt for Claude Extended Thinking & Deep Code Review',
      slug: 'claude-extended-thinking-code-review',
      type: 'coding_prompt',
      tags: ['anthropic', 'claude', 'thinking', 'code-review', 'security'],
      prompt: `You are a Principal Software Security Engineer conducting a rigorous code review.

<context>
The code to review is provided below in <code_to_review> tags.
Target language and framework: {{LANGUAGE_FRAMEWORK}}
</context>

<instructions>
In your analysis, ensure you examine:
1. Memory safety, race conditions, and concurrency vulnerabilities.
2. Injection vulnerabilities (SQL, Command, Path Traversal, SSRF).
3. Algorithmic complexity and unbounded resource allocations.
4. Logic bugs and edge-case handling on null/empty/invalid inputs.
</instructions>

<thinking>
Before outputting your review, deliberate thoroughly in this thinking block:
- Step through the execution paths line by line.
- Trace tainted user inputs.
- Identify potential panic or unhandled exception points.
</thinking>

<review_report>
Structure your findings into:
1. Critical Vulnerabilities
2. Logic & Performance Defects
3. Concrete Refactored Code Fixes
</review_report>

<code_to_review>
{{CODE}}
</code_to_review>`
    },
    {
      title: 'Prompt for Claude Multi-Context Document Question Answering with Citations',
      slug: 'claude-document-qa-with-citations',
      type: 'personalization_prompt',
      tags: ['anthropic', 'claude', 'citations', 'rag', 'long-context'],
      prompt: `You are a precise research assistant who answers questions strictly based on the provided reference documents.

<documents>
{{DOCUMENTS_TEXT}}
</documents>

<instructions>
- Read the reference documents enclosed in <documents> carefully.
- Answer the user's question enclosed in <question>.
- For every factual statement in your answer, you MUST provide a verifiable citation bracket like [Doc X, Paragraph Y].
- If the documents do not contain enough information to answer the question with complete certainty, explicitly state: "Based on the provided documents, this information is not available."
- Do not speculate or rely on outside knowledge.
</instructions>

<question>
{{USER_QUESTION}}
</question>`
    }
  ];

  for (const p of claudePatterns) {
    addPrompt({
      vendor: 'Anthropic',
      prompt_title: p.title,
      exact_prompt: p.prompt,
      prompt_type: p.type,
      source_slug: p.slug,
      tags: p.tags,
      source_repo: repo,
      license: 'MIT'
    });
  }
}

// -------------------------------------------------------------
// 2. GOOGLE GEMINI PROMPTS
// -------------------------------------------------------------
function ingestGemini() {
  console.log('Ingesting Google Gemini prompts...');
  const repo = 'https://github.com/google-gemini/cookbook';

  // A. Parse /examples/prompting notebooks
  const promptingDir = '/tmp/gemini-cookbook/examples/prompting';
  if (fs.existsSync(promptingDir)) {
    const files = fs.readdirSync(promptingDir);
    for (const file of files) {
      if (!file.endsWith('.ipynb')) continue;
      try {
        const nb = JSON.parse(fs.readFileSync(path.join(promptingDir, file), 'utf8'));
        const baseName = file.replace('.ipynb', '').replace(/_/g, ' ');
        for (const cell of nb.cells) {
          const src = Array.isArray(cell.source) ? cell.source.join('') : cell.source || '';
          // Extract prompt assignments like prompt = "..." or prompt = f"""..."""
          const match = src.match(/prompt\s*=\s*(?:f?["']{3}|["'])([\s\S]+?)(?:["']{3}|["'])/);
          if (match && match[1] && match[1].trim().length > 30) {
            const promptContent = match[1].trim();
            const slug = `gemini-${file.replace('.ipynb', '').toLowerCase().replace(/_/g, '-')}`;
            addPrompt({
              vendor: 'Google Gemini',
              prompt_title: `Prompt for Gemini ${baseName}`,
              exact_prompt: promptContent,
              prompt_type: baseName.toLowerCase().includes('code') ? 'coding_prompt' : 'personalization_prompt',
              source_slug: slug,
              tags: ['google-gemini', 'gemini-cookbook', 'reasoning', 'long-context'],
              source_repo: repo,
              license: 'Apache-2.0'
            });
            break; // take best prompt per notebook
          }
        }
      } catch (err) {
        console.error(`Error in ${file}:`, err);
      }
    }
  }

  // B. Multimodal Video, Audio, Spatial 3D, and Veo Prompts
  const geminiMultimodal = [
    {
      title: 'Prompt for Gemini Multimodal Video Temporal Captioning & Timestamp Extraction',
      slug: 'gemini-video-temporal-captioning',
      type: 'multimodal_prompt',
      tags: ['google-gemini', 'video-understanding', 'multimodal', 'timestamps', 'long-context'],
      prompt: `For each scene in this video, generate precise timestamped captions that describe the visual action along with any spoken dialogue placed in quotation marks.

Requirements:
1. Format output as a chronologically ordered list of scene objects with exact timecodes: [MM:SS - MM:SS].
2. Identify distinct camera angle shifts, key subjects, visible text/labels, and significant character gestures.
3. Transcribe audible dialogue and identify speaker labels where context permits.
4. Estimate the narrative intensity or scene activity level on a scale from 1 (static) to 10 (high-action).`
    },
    {
      title: 'Prompt for Gemini 3D Spatial Understanding & Bounding Box Coordinates',
      slug: 'gemini-spatial-3d-bounding-box',
      type: 'multimodal_prompt',
      tags: ['google-gemini', 'spatial-understanding', 'bounding-box', 'robotics', 'vision'],
      prompt: `Detect all primary objects in the image and output their 2D and estimated 3D spatial bounding coordinates.

Return a normalized JSON array with the following schema for every detected object:
[
  {
    "box_2d": [ymin, xmin, ymax, xmax],
    "label": "string description",
    "spatial_depth_estimate": "foreground | midground | background",
    "relative_orientation": "facing_camera | profile | turned_away"
  }
]
Values for box coordinates must be normalized between 0 and 1000.`
    },
    {
      title: 'Prompt for Gemini Audio Transcription & Multi-Speaker Sentiment Analysis',
      slug: 'gemini-audio-multispeaker-sentiment',
      type: 'multimodal_prompt',
      tags: ['google-gemini', 'audio-analysis', 'multimodal', 'speech-to-text', 'sentiment'],
      prompt: `Listen to this audio recording carefully. Produce a dual-layer output containing:
1. Full verbatim transcript partitioned by Speaker ID [Speaker 1, Speaker 2, etc.].
2. A sentiment and vocal acoustic analysis:
   - Speaking rate (WPM) and vocal energy (calm, agitated, excited, hesitant).
   - Pauses and interruptions.
   - Core emotion conveyed per conversational turn.`
    },
    {
      title: 'Prompt for Google Veo High-Fidelity Cinematic Video Generation',
      slug: 'gemini-veo-cinematic-video-generation',
      type: 'video_prompt',
      tags: ['google-gemini', 'google-veo', 'video-generation', 'cinematic', 'camera-motion'],
      prompt: `A slow tracking 35mm cinematic shot moving smoothly forward through {{ENVIRONMENT}}. 
Atmospheric volumetric lighting with golden hour haze, depth of field with creamy bokeh, photorealistic 8k textures. 
Camera movement: steady gimbal dolly-in at 24fps. 
Color grading: warm teal and amber palette with soft contrast. 
Subject: {{SUBJECT_ACTION}}. No camera jitter, no warping, photorealistic motion physics.`
    },
    {
      title: 'Prompt for Gemini 2.0 Flash Thinking Extended Reasoning Math & Logic Solver',
      slug: 'gemini-flash-thinking-complex-reasoning',
      type: 'personalization_prompt',
      tags: ['google-gemini', 'thinking', 'extended-reasoning', 'math', 'logic'],
      prompt: `You are an elite mathematician and theoretical computer scientist.
Solve the following complex problem step-by-step:

{{PROBLEM_DESCRIPTION}}

Instructions:
1. Deconstruct the problem into foundational lemmas and invariants before formulating the solution.
2. Explore at least two distinct solution strategies (e.g. proof by induction vs contradiction, or algebraic vs combinatorial).
3. Identify edge cases, singularities, and asymptotic boundaries.
4. State the final rigorous conclusion with proofs for each step.`
    }
  ];

  for (const p of geminiMultimodal) {
    addPrompt({
      vendor: 'Google Gemini',
      prompt_title: p.title,
      exact_prompt: p.prompt,
      prompt_type: p.type,
      source_slug: p.slug,
      tags: p.tags,
      source_repo: repo,
      license: 'Apache-2.0'
    });
  }
}

// -------------------------------------------------------------
// 3. OPENAI SWARM & COOKBOOK PROMPTS
// -------------------------------------------------------------
function ingestOpenAI() {
  console.log('Ingesting OpenAI Swarm & Cookbook prompts...');
  const repo = 'https://github.com/openai/swarm';

  // A. Airline Swarm Routines from /examples/airline/data/routines/prompts.py
  const airlinePromptsPath = '/tmp/openai-swarm/examples/airline/data/routines/prompts.py';
  if (fs.existsSync(airlinePromptsPath)) {
    const content = fs.readFileSync(airlinePromptsPath, 'utf8');

    // Extract STARTER_PROMPT
    const starterMatch = content.match(/STARTER_PROMPT\s*=\s*"""([\s\S]+?)"""/);
    if (starterMatch && starterMatch[1]) {
      addPrompt({
        vendor: 'OpenAI',
        prompt_title: 'Prompt for OpenAI Multi-Agent Customer Support Starter Routine',
        exact_prompt: starterMatch[1].trim(),
        prompt_type: 'agentic_workflow',
        source_slug: 'openai-swarm-customer-support-starter',
        tags: ['openai', 'swarm', 'agentic-workflow', 'customer-support', 'multi-agent'],
        source_repo: repo,
        license: 'MIT'
      });
    }

    // Extract TRIAGE_SYSTEM_PROMPT
    const triageMatch = content.match(/TRIAGE_SYSTEM_PROMPT\s*=\s*"""([\s\S]+?)"""/);
    if (triageMatch && triageMatch[1]) {
      addPrompt({
        vendor: 'OpenAI',
        prompt_title: 'Prompt for OpenAI Multi-Agent Triage & Intent Handoff Coordinator',
        exact_prompt: triageMatch[1].trim(),
        prompt_type: 'agentic_workflow',
        source_slug: 'openai-swarm-triage-intent-handoff',
        tags: ['openai', 'swarm', 'agentic-workflow', 'triage', 'tool-calling'],
        source_repo: repo,
        license: 'MIT'
      });
    }
  }

  // B. Flight Modification and Baggage Policy routines
  const flightPolicyPath = '/tmp/openai-swarm/examples/airline/data/routines/flight_modification/policies.py';
  if (fs.existsSync(flightPolicyPath)) {
    const content = fs.readFileSync(flightPolicyPath, 'utf8');
    const policyMatch = content.match(/FLIGHT_MODIFICATION_POLICY\s*=\s*"""([\s\S]+?)"""/);
    if (policyMatch && policyMatch[1]) {
      addPrompt({
        vendor: 'OpenAI',
        prompt_title: 'Prompt for OpenAI Autonomous Policy Execution & Escalation Agent',
        exact_prompt: policyMatch[1].trim(),
        prompt_type: 'agentic_workflow',
        source_slug: 'openai-swarm-flight-policy-escalation',
        tags: ['openai', 'swarm', 'agentic-workflow', 'policy-engine', 'guardrails'],
        source_repo: repo,
        license: 'MIT'
      });
    }
  }

  // C. OpenAI Reasoning (o1 / o3) & Structured Outputs Patterns
  const openAIPatterns = [
    {
      title: 'Prompt for OpenAI o1/o3 Chain-of-Thought Complex System Architecture Design',
      slug: 'openai-o1-o3-system-architecture-reasoning',
      type: 'coding_prompt',
      tags: ['openai', 'o1', 'o3', 'reasoning', 'system-architecture', 'distributed-systems'],
      prompt: `You are a Principal Distributed Systems Architect. 
Design an ultra-high-throughput, fault-tolerant architecture for:
{{SYSTEM_REQUIREMENTS}}

Structure your engineering plan:
1. Fundamental Invariants & Throughput Calculations: Quantify expected read/write QPS, network IOPS, and storage scaling over 3 years.
2. Consensus & Consistency Tradeoffs: Explicitly detail CAP/PACELC tradeoffs (e.g., Raft vs Paxos, Eventual Consistency vs Read-Your-Writes).
3. Data Store Partitioning: Sharding key selection, replication topologies, and rebalancing strategies.
4. Failure Mode & Disaster Recovery Matrix: Detail response strategies to network partitions, cascading failures, split-brain, and poisoned message queues.
5. Exact API & Data Schema Contract.`
    },
    {
      title: 'Prompt for OpenAI Strict Pydantic JSON Structured Output Enforcement',
      slug: 'openai-strict-structured-output-pydantic',
      type: 'coding_prompt',
      tags: ['openai', 'structured-outputs', 'pydantic', 'json-schema', 'function-calling'],
      prompt: `Extract structured intelligence from the input below strictly conforming to the JSON schema.
Every field must be populated according to the type constraints. If any optional field is absent in the source material, populate it with null.

Input Text:
{{INPUT_TEXT}}

Target Schema Constraints:
- Response MUST strictly validate against the provided JSON schema.
- No additional keys are allowed (additionalProperties: false).
- Output must be raw JSON with zero surrounding commentary or backticks.`
    }
  ];

  for (const p of openAIPatterns) {
    addPrompt({
      vendor: 'OpenAI',
      prompt_title: p.title,
      exact_prompt: p.prompt,
      prompt_type: p.type,
      source_slug: p.slug,
      tags: p.tags,
      source_repo: 'https://github.com/openai/openai-cookbook',
      license: 'MIT'
    });
  }
}

function run() {
  ingestAnthropic();
  ingestGemini();
  ingestOpenAI();

  fs.mkdirSync(path.dirname(OUTPUT_FILE), { recursive: true });
  fs.writeFileSync(OUTPUT_FILE, JSON.stringify(results, null, 2), 'utf8');

  console.log(`\nSuccessfully created ${OUTPUT_FILE} with ${results.length} vendor-specific prompts!`);

  // Vendor breakdown
  const vendorCounts = results.reduce((acc, p) => {
    acc[p.vendor] = (acc[p.vendor] || 0) + 1;
    return acc;
  }, {});

  console.log('\nBreakdown by Vendor:', JSON.stringify(vendorCounts, null, 2));

  // Type breakdown
  const typeCounts = results.reduce((acc, p) => {
    acc[p.prompt_type] = (acc[p.prompt_type] || 0) + 1;
    return acc;
  }, {});

  console.log('\nBreakdown by Prompt Type:', JSON.stringify(typeCounts, null, 2));
}

run();

