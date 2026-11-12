import enum

class AssetType(str, enum.Enum):
    PROMPT = "PROMPT"                     # Text prompts (System, Creative, Persona, Coding, Music, Video, Image)
    SKILL = "SKILL"                       # SKILL.md bundles (Vercel, Antigravity, Claude, GameDev)
    MCP_CONFIG = "MCP_CONFIG"             # mcp.json / mcpServers JSON blocks
    SUBAGENT = "SUBAGENT"                 # .claude/agents/*.md & .github/agents/*.md
    SLASH_COMMAND = "SLASH_COMMAND"       # .claude/commands/*.md
    IDE_RULE = "IDE_RULE"                 # .cursorrules & .mdc rules
    DESIGN_SPEC = "DESIGN_SPEC"           # DESIGN.md design system specifications
    CUSTOM_GPT = "CUSTOM_GPT"             # Custom GPT definitions with JSON schemas
    WORKFLOW = "WORKFLOW"                 # ComfyUI, n8n, Make node graphs
    ENGINEERING_LOOP = "ENGINEERING_LOOP" # Deterministic state-machine loop configurations

class UserTier(str, enum.Enum):
    FREE = "FREE"
    PRO = "PRO"
    ADMIN = "ADMIN"

class SubscriptionStatus(str, enum.Enum):
    PENDING = "PENDING"
    ACTIVE = "ACTIVE"
    PAST_DUE = "PAST_DUE"
    CANCELED = "CANCELED"
    TRIALING = "TRIALING"

class SubscriptionGateway(str, enum.Enum):
    PADDLE = "PADDLE"      # Read legacy records only; new checkouts never use Paddle.
    RAZORPAY = "RAZORPAY"  # Platform's own Razorpay account (Indian users, INR)
    DODO = "DODO"          # Platform's own Dodo Payments account (foreign users, USD)

class SellerGateway(str, enum.Enum):
    RAZORPAY = "RAZORPAY"  # Seller's own Razorpay account
    DODO = "DODO"          # Seller's own Dodo Payments account

class CheckoutStatus(str, enum.Enum):
    PENDING = "PENDING"
    PAID = "PAID"
    EXPIRED = "EXPIRED"
    FAILED = "FAILED"

class OAuthProvider(str, enum.Enum):
    EMAIL = "EMAIL"
    GOOGLE = "GOOGLE"

class SourceType(str, enum.Enum):
    INGESTED = "INGESTED"
    USER_CREATED = "USER_CREATED"

class CollectionVisibility(str, enum.Enum):
    PUBLIC = "PUBLIC"
    PRIVATE = "PRIVATE"

class PurchaseStatus(str, enum.Enum):
    PENDING = "PENDING"
    COMPLETED = "COMPLETED"
    REFUNDED = "REFUNDED"
