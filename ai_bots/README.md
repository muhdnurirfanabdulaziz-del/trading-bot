# ai_bots — 4 AI bots for the trading project (Claude Sonnet 4.6)

A **self-contained** folder. It does **not** touch or import the parent
trading-bot files — everything it needs is here (`market.py` is a standalone
copy of the price-fetch + strategy logic). Delete this folder and the original
project is unchanged.

All four bots run on **`claude-sonnet-4-6`** ("v.6").

## Setup (once)

```bash
cd ai_bots
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...   # see "Getting an API key" below
```

## The 4 bots — what each is and how to use it

| # | File | AI layer | Run it |
|---|------|----------|--------|
| 1 | `bot1_chat.py` | Chatbot + personality (Layer 1) | `python bot1_chat.py` |
| 2 | `bot2_explainer.py` | System prompt + few-shot (Layer 4) | `python bot2_explainer.py` |
| 3 | `bot3_agent.py` | Agent + tools (Layer 2) | `python bot3_agent.py` |
| 4 | `bot4_rag.py` | RAG over your notes (Layer 3) | `python bot4_rag.py "your question"` |

### Bot 1 — Conversational assistant
An interactive chat loop ("TradeBuddy") with a custom personality and memory of
the conversation. Type questions, type `quit` to exit. **Use it** when you just
want to *talk* to an AI about trading.

### Bot 2 — Signal explainer
Fetches the latest price, runs the strategy, and asks Claude to explain the
signal in a fixed 3-sentence format. The format is locked with a system prompt +
one worked example — no training. **Use it** for consistent, single-purpose output.

### Bot 3 — Tool-using agent
Claude is given two tools (`fetch_prices`, `run_strategy`) and decides when to
call them to answer your question. This is the jump from "talks" to "does." **Use
it / extend it** by adding more tools (e.g. `place_paper_trade`).

### Bot 4 — Document Q&A (RAG)
Answers questions using only `notes.md`. Edit `notes.md` to add your own strategy
knowledge and the bot answers from it. **Use it** to make the AI an expert on
*your* material. Uses simple keyword retrieval — swap in embeddings if notes grow.

## What Sonnet 4.6 ("v.6") lacks in AI power

Sonnet 4.6 is the **speed + cost sweet spot** ($3 / $15 per 1M tokens, 1M context).
For these bots it's more than enough. Compared to the top-tier models
(**Opus 4.8**, **Fable 5**) you give up:

- **Top-end reasoning ceiling** — on the hardest, long-horizon, deeply autonomous
  tasks, Opus 4.8 and Fable 5 are noticeably stronger. For chat, explanations, and
  a handful of tools, you won't feel the gap.
- **Max output length** — 64K tokens vs 128K on Opus/Fable (irrelevant for short
  answers like these).
- **A few advanced features** — no *fast mode*, no *task budgets*, and no
  *mid-conversation system messages* (all Opus-4.7/4.8-only).

It **does** have: adaptive thinking, the `effort` parameter (`low`→`max`), tool
use, RAG, prompt caching, and structured outputs. If you later want maximum
intelligence, change one line — `MODEL = "claude-opus-4-8"` — in any bot.

## Getting an API key (I can't do this part for you)

An API key is tied to *your* Anthropic account, so you have to create it — I
can't fetch or generate one, and you should never paste a key into code or share
it. Steps (2 minutes):

1. Go to **https://console.anthropic.com** and sign in (or sign up).
2. Open **Settings → API keys → Create key**, name it, and copy it
   (it's shown only once — starts with `sk-ant-`).
3. Add credit under **Billing** (the API is pay-as-you-go; these bots cost
   fractions of a cent per run).
4. Make it available to the bots:
   ```bash
   export ANTHROPIC_API_KEY=sk-ant-your-key-here
   ```
   (add that line to your `~/.bashrc` / `~/.zshrc` to keep it set).

The SDK reads `ANTHROPIC_API_KEY` automatically — no code change needed.
