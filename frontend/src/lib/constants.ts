export interface CategoryConfig {
  slug: string;
  name: string;
  badge: string;
  badgeColor?: string;
  itemCountLabel: string;
  description: string;
  subcategories: {
    slug: string;
    name: string;
    description: string;
  }[];
}

export const CATEGORIES: CategoryConfig[] = [
  {
    slug: "prompts",
    name: "Prompts",
    badge: "20.4K+",
    badgeColor: "bg-amber-500",
    itemCountLabel: "20,490 Items",
    description: "Text templates designed for direct chat injection with dynamic {{variables}}.",
    subcategories: [
      {
        slug: "all",
        name: "All Prompts",
        description: "Browse all 20,490 prompt templates across every discipline.",
      },
      {
        slug: "system-base-contexts",
        name: "System & Base Contexts",
        description: "Baseline directives for OpenAI, Claude, Grok, v0, Cursor, Devin",
      },
      {
        slug: "creative-writing-fiction",
        name: "Creative Writing & Fiction",
        description: "Sci-Fi, Fantasy, Horror, Screenwriting, Worldbuilding",
      },
      {
        slug: "personas-teachers-roleplay",
        name: "Personas, Teachers & Roleplay",
        description: "First-principles tutors, historical figures, debaters, game NPCs",
      },
      {
        slug: "visual-art-image-generation",
        name: "Visual Art & Image Generation",
        description: "Midjourney v6, Flux.1, SDXL, Stable Diffusion",
      },
      {
        slug: "coding-software-engineering",
        name: "Coding & Software Engineering",
        description: "Fullstack, refactoring, code review, game logic",
      },
      {
        slug: "cinematic-video-camera-movements",
        name: "Cinematic Video & Camera Movements",
        description: "Runway Gen-3, Luma, Kling, Sora, Wan 2.1",
      },
      {
        slug: "ai-music-lyrics",
        name: "AI Music & Lyrics",
        description: "Suno v5/v6, Udio, Google Lyria, ElevenLabs SSML",
      },
      {
        slug: "vendor-benchmarks",
        name: "Vendor Benchmarks",
        description: "Canonical evaluation sets and standardized comparison runs",
      },
    ],
  },
  {
    slug: "skills",
    name: "Agentic Skills",
    badge: "HOT",
    badgeColor: "bg-red-500",
    itemCountLabel: "6,442 Items",
    description: "Self-contained SKILL.md packages with YAML frontmatter, execution instructions, and tool definitions.",
    subcategories: [
      {
        slug: "all",
        name: "All Skills",
        description: "Browse all 6,442 agentic skills and SKILL.md execution packages.",
      },
      {
        slug: "fullstack-backend-engineering",
        name: "Fullstack & Backend Engineering",
        description: "Next.js, Node, Python FastAPI, Go, Rust, PostgreSQL, Drizzle",
      },
      {
        slug: "frontend-motion-design",
        name: "Frontend & Motion Design",
        description: "Vercel React best practices, View Transitions, ibelick motion, 21st.dev",
      },
      {
        slug: "anti-ai-slop-design-discipline",
        name: "Anti-AI-Slop Design Discipline",
        description: "Anthropic design guidelines, custom tokens, typography pairings",
      },
      {
        slug: "game-development",
        name: "Game Development",
        description: "Godot 4, Unity 6, Unreal Engine 5, Three.js WebGL, Bevy, Roblox Luau",
      },
      {
        slug: "devops-cloud",
        name: "DevOps & Cloud",
        description: "Docker, Kubernetes, Terraform, AWS CDK, GCP Cloud Run, GitHub Actions",
      },
      {
        slug: "security-compliance",
        name: "Security & Compliance",
        description: "Threat modeling, vulnerability scanning, penetration testing, GDPR",
      },
      {
        slug: "browser-automation",
        name: "Browser Automation",
        description: "Playwright, Stagehand, Firecrawl scrapers",
      },
    ],
  },
  {
    slug: "mcp-configs",
    name: "MCP Configs",
    badge: "NEW",
    badgeColor: "bg-amber-500",
    itemCountLabel: "4,370 Items",
    description: 'Ready-to-copy "mcpServers" JSON blocks with commands (npx, uvx, docker), args, environment variables, and tool schemas.',
    subcategories: [
      {
        slug: "all",
        name: "All MCP Configs",
        description: "Browse all 4,370 Model Context Protocol configurations.",
      },
      {
        slug: "databases-vector-stores",
        name: "Databases & Vector Stores",
        description: "Postgres, SQLite, Redis, Supabase, Pinecone, Neo4j",
      },
      {
        slug: "developer-tools-git",
        name: "Developer Tools & Git",
        description: "GitHub MCP, GitLab, Docker, Kubernetes, Sentry",
      },
      {
        slug: "game-engines-3d",
        name: "Game Engines & 3D",
        description: "Unity 6 Editor MCP, Godot 4 MCP, Blender 3D Poly Haven / Rodin MCP",
      },
      {
        slug: "browser-scraping",
        name: "Browser & Scraping",
        description: "Playwright MCP, Puppeteer, Browserbase, Brave Search",
      },
      {
        slug: "cloud-infrastructure",
        name: "Cloud Infrastructure",
        description: "AWS, Google Cloud, Cloudflare Workers, Vercel",
      },
      {
        slug: "productivity-saas",
        name: "Productivity & SaaS",
        description: "Linear, Jira, Notion, Slack, Google Drive, Asana",
      },
      {
        slug: "security-financial",
        name: "Security & Financial",
        description: "Pay-per-call x402 tools, blockchain RPCs, static analysis",
      },
    ],
  },
  {
    slug: "agents-commands",
    name: "Subagents & Commands",
    badge: "838",
    badgeColor: "bg-blue-500",
    itemCountLabel: "838 Items",
    description: "Ready-to-drop subagent configurations and interactive command templates.",
    subcategories: [
      {
        slug: "all",
        name: "All Agents & Commands",
        description: "Browse all subagents and command manifests.",
      },
      {
        slug: "specialized-subagents",
        name: "Specialized Subagents",
        description: ".claude/agents/*.md, .github/agents/*.md, BMAD orchestrators (Security, DB, PRs)",
      },
      {
        slug: "interactive-slash-commands",
        name: "Slash Commands",
        description: ".claude/commands/*.md, SuperClaude, Shakacode (/review-pr, /spawn, /multi-plan)",
      },
    ],
  },
  {
    slug: "ide-design-specs",
    name: "IDE Rules & Design",
    badge: "585",
    badgeColor: "bg-purple-500",
    itemCountLabel: "585 Items",
    description: "Machine-readable developer rules and company design tokens read by agents during active editing.",
    subcategories: [
      {
        slug: "all",
        name: "All Rules & Specs",
        description: "Browse all framework rules, UI systems, and directives.",
      },
      {
        slug: "framework-ide-rules",
        name: "Framework IDE Rules",
        description: ".cursorrules and .mdc files (Next.js 15, React 19, Svelte 5, Tailwind v4, Expo)",
      },
      {
        slug: "company-ui-ux-systems",
        name: "Company UI/UX Systems",
        description: "Official DESIGN.md specs (Apple, Vercel, Supabase, Stripe, Linear, Airbnb)",
      },
      {
        slug: "cross-agent-directives",
        name: "Cross-Agent Directives",
        description: "AGENTS.md, GEMINI.md, CLAUDE.md monorepo standards and lifecycle hooks",
      },
    ],
  },
  {
    slug: "custom-gpts",
    name: "Custom GPTs",
    badge: "1.2K",
    badgeColor: "bg-indigo-500",
    itemCountLabel: "1,255 Items",
    description: "Exported Custom GPT specifications from the System Prompt Library containing rich capability flags.",
    subcategories: [
      {
        slug: "all",
        name: "All Custom GPTs",
        description: "Browse all 1,255 Custom GPT schemas and system configurations.",
      },
      {
        slug: "structured-output-json-schema",
        name: "Structured Output & JSON Schema",
        description: "Agents tuned for high-precision Pydantic / JSON schema guarantees",
      },
      {
        slug: "multimodal-agents",
        name: "Multimodal Agents",
        description: "Vision, Audio, and Real-time Voice/TTS agents",
      },
      {
        slug: "tool-calling-workflow-agents",
        name: "Tool-Calling & Workflow Agents",
        description: "n8n integrations, external REST APIs, and automated MCP tool calling",
      },
      {
        slug: "data-science-code-interpreter",
        name: "Data Science & Code Interpreter",
        description: "Pandas, NumPy, data viz, math theorem provers, and execution environments",
      },
    ],
  },
  {
    slug: "workflows",
    name: "Workflows",
    badge: "548",
    badgeColor: "bg-pink-500",
    itemCountLabel: "548 Items",
    description: "Importable node graphs and visual automation blueprints.",
    subcategories: [
      {
        slug: "all",
        name: "All Workflows",
        description: "Browse all 548 importable node graphs and automation blueprints.",
      },
      {
        slug: "comfyui-workflows",
        name: "ComfyUI Workflows",
        description: "Flux.1 Dev/Schnell, SDXL, Wan 2.1 video, ControlNet, FaceID",
      },
      {
        slug: "n8n-automation-blueprints",
        name: "n8n Automation Blueprints",
        description: "Webhook triggers, autonomous agent loops, CRM sync",
      },
      {
        slug: "make-langflow-graphs",
        name: "Make.com & Langflow Graphs",
        description: "Multi-step automation pipelines and Dify DSL configs",
      },
    ],
  },
  {
    slug: "loops",
    name: "Verification Loops",
    badge: "TRY ME",
    badgeColor: "bg-amber-500",
    itemCountLabel: "26 Items",
    description: "YAML state machines and Python/Rust loop controllers with retry budgets, bash execution, and exit-code gates.",
    subcategories: [
      {
        slug: "all",
        name: "All Loops",
        description: "Browse deterministic self-correcting engineering loops.",
      },
      {
        slug: "compiler-ast-repair-loops",
        name: "Compiler & AST Repair Loops",
        description: "SWE-agent, Mini-SWE-agent (cargo check, gcc, ruff)",
      },
      {
        slug: "test-driven-repair-loops",
        name: "Test-Driven Repair Loops",
        description: "AlphaCodium, LangGraph Reflexion, OpenHands",
      },
      {
        slug: "self-healing-dom-scraping-loops",
        name: "Self-Healing DOM Scraping Loops",
        description: "Stagehand, Browser-Use (Pydantic schema retries)",
      },
      {
        slug: "goal-directed-ledger-engines",
        name: "Goal-Directed Ledger Engines",
        description: "Rust Zeroshot ledger, Loop-Engine DAGs",
      },
    ],
  },
];

