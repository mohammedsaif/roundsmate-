#!/usr/bin/env python3
"""Generate RoundsMate Phase 7 submission assets."""
import os
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Circle, RegularPolygon

os.makedirs('assets', exist_ok=True)

# ── Palette ───────────────────────────────────────────────────────────────────
BG       = '#060a14'
NODE_BG  = '#0e1929'
SEC_CLR  = '#b84000'
HITL_CLR = '#0d47a1'
AGENT_BG = '#092010'
BLOCK_BG = '#5c0a0a'
MCP_BG   = '#1a0635'
TEXT_HI  = '#f0f5ff'
TEXT_LO  = '#7a9ab0'
NEON_G   = '#00e5a0'
NEON_B   = '#00b0f0'
NEON_P   = '#b44aef'
NEON_O   = '#ff6b35'
ARROW_C  = '#3a5a7a'


def node(ax, cx, cy, w, h, title, sub='', bg=NODE_BG, border=NEON_B, fs=7.5):
    ax.add_patch(FancyBboxPatch(
        (cx - w / 2, cy - h / 2), w, h,
        boxstyle='round,pad=0.005', facecolor=bg, edgecolor=border,
        linewidth=1.8, transform=ax.transAxes, zorder=3, alpha=0.93,
    ))
    yoff = h * 0.14 if sub else 0
    ax.text(cx, cy + yoff, title, ha='center', va='center', color=TEXT_HI,
            fontsize=fs, fontweight='bold', transform=ax.transAxes, zorder=4)
    if sub:
        ax.text(cx, cy - h * 0.22, sub, ha='center', va='center', color=TEXT_LO,
                fontsize=max(fs - 1.5, 5.5), transform=ax.transAxes, zorder=4)


def arr(ax, x1, y1, x2, y2, label='', clr=ARROW_C, rad=0.0):
    ax.annotate('', xy=(x2, y2), xytext=(x1, y1),
                xycoords='axes fraction', textcoords='axes fraction',
                arrowprops=dict(arrowstyle='->', color=clr, lw=1.4,
                                connectionstyle=f'arc3,rad={rad}'), zorder=2)
    if label:
        ax.text((x1 + x2) / 2, (y1 + y2) / 2 + 0.015, label,
                ha='center', va='bottom', color=NEON_G, fontsize=6,
                style='italic', transform=ax.transAxes, zorder=5)


# ═══════════════════════════════════════════════════════════════════════════════
# ARCHITECTURE DIAGRAM  1920 × 1080
# ═══════════════════════════════════════════════════════════════════════════════
fig, ax = plt.subplots(figsize=(19.2, 10.8), dpi=100)
fig.patch.set_facecolor(BG)
ax.set_facecolor(BG)
ax.set_xlim(0, 1); ax.set_ylim(0, 1); ax.axis('off')

# Header
ax.text(0.5, 0.962, 'RoundsMate — Agent Workflow',
        ha='center', va='top', color=TEXT_HI, fontsize=20, fontweight='bold',
        transform=ax.transAxes)
ax.text(0.5, 0.928, 'ADK 2.0 Workflow  ·  5 LlmAgents  ·  5 MCP Tools  ·  Security Checkpoint  ·  HITL Approval Gate',
        ha='center', va='top', color=TEXT_LO, fontsize=10, transform=ax.transAxes)
ax.plot([0.02, 0.98], [0.910, 0.910], color='#1e3a5f', lw=1, transform=ax.transAxes)

NW, NH = 0.105, 0.093

# START
ax.add_patch(Circle((0.045, 0.545), 0.024, color=NEON_G, alpha=0.9,
                     transform=ax.transAxes, zorder=3))
ax.text(0.045, 0.545, 'START', ha='center', va='center', color='#000',
        fontsize=7, fontweight='bold', transform=ax.transAxes, zorder=4)

# security_checkpoint
node(ax, 0.178, 0.545, NW, NH, 'security_checkpoint',
     'PII scrub · injection detect · audit log', SEC_CLR, '#ff9955', 7.5)

# blocked_output
node(ax, 0.178, 0.185, NW * 0.84, NH * 0.72, 'blocked_output',
     'SECURITY_EVENT terminal', BLOCK_BG, '#ff4444', 6.8)

# intent_classifier
node(ax, 0.316, 0.545, NW, NH, 'intent_classifier',
     'Classifies task type', NODE_BG, NEON_B, 7.5)

# router
node(ax, 0.434, 0.545, NW * 0.74, NH * 0.74, 'router',
     'Routes by task_type', NODE_BG, NEON_G, 7)

# Specialist agents
SX = 0.597
specs = [
    (0.840, 'handoff_note_agent',   'SOAP notes  ·  Drive MCP'),
    (0.635, 'drug_lookup_agent',    'Drug interactions  ·  Drug DB MCP'),
    (0.430, 'schedule_agent',       'Calendar optimizer  ·  Calendar MCP'),
    (0.225, 'comms_drafter_agent',  'Letters & drafts  ·  Gmail MCP'),
]
for sy, sname, sdesc in specs:
    node(ax, SX, sy, NW * 1.1, NH, sname, sdesc, AGENT_BG, NEON_G, 7.5)

# MCP Server panel (dotted border)
MPX, MPY, MPW, MPH = 0.726, 0.533, 0.076, 0.580
ax.add_patch(FancyBboxPatch(
    (MPX - MPW / 2, MPY - MPH / 2), MPW, MPH,
    boxstyle='round,pad=0.007', facecolor=MCP_BG, edgecolor=NEON_P,
    linewidth=1.5, linestyle='--', alpha=0.82, transform=ax.transAxes, zorder=2,
))
ax.text(MPX, MPY + MPH / 2 - 0.022, 'MCP Server', ha='center', va='top',
        color=NEON_P, fontsize=9, fontweight='bold', transform=ax.transAxes, zorder=3)
ax.text(MPX, MPY + MPH / 2 - 0.052, 'stdio transport', ha='center', va='top',
        color=TEXT_LO, fontsize=6.5, transform=ax.transAxes, zorder=3)
for i, tool in enumerate(['get_patient_file', 'lookup_drug_interaction',
                           'list_calendar_events', 'create_calendar_event',
                           'create_gmail_draft']):
    ax.text(MPX, MPY + MPH / 2 - 0.092 - i * 0.087,
            f'◆  {tool}', ha='center', va='center', color='#ce93d8',
            fontsize=6, transform=ax.transAxes, zorder=3)

# approval_gate
node(ax, 0.854, 0.533, NW * 1.06, NH, 'approval_gate',
     'Doctor reviews  ·  approve / reject', HITL_CLR, '#64b5f6', 7.5)
ax.text(0.854, 0.467, '[HITL]  Human-in-the-Loop', ha='center', va='top',
        color='#90caf9', fontsize=6.5, style='italic', transform=ax.transAxes)

# final_output
node(ax, 0.966, 0.533, NW * 0.70, NH * 0.72, 'final_output',
     'Formatted result', NODE_BG, NEON_G, 7)

# ── Arrows ────────────────────────────────────────────────────────────────────
arr(ax, 0.069, 0.545, 0.125, 0.545)
arr(ax, 0.231, 0.545, 0.263, 0.545, 'PASS')
arr(ax, 0.369, 0.545, 0.397, 0.545)

# security → blocked
ax.annotate('', xy=(0.178, 0.230), xytext=(0.178, 0.499),
            xycoords='axes fraction', textcoords='axes fraction',
            arrowprops=dict(arrowstyle='->', color='#cc3333', lw=1.4), zorder=2)
ax.text(0.148, 0.365, 'BLOCKED', ha='right', va='center', color='#ff6666',
        fontsize=6, style='italic', transform=ax.transAxes)

# router → specialists
for sy, _, _ in specs:
    ax.annotate('', xy=(SX - NW * 1.1 / 2, sy), xytext=(0.471, 0.545),
                xycoords='axes fraction', textcoords='axes fraction',
                arrowprops=dict(arrowstyle='->', color=ARROW_C, lw=1.2,
                                connectionstyle='arc3,rad=0'), zorder=2)

# specialists → approval_gate
for sy, _, _ in specs:
    ax.annotate('', xy=(0.854 - NW * 1.06 / 2, 0.533),
                xytext=(SX + NW * 1.1 / 2, sy),
                xycoords='axes fraction', textcoords='axes fraction',
                arrowprops=dict(arrowstyle='->', color=ARROW_C, lw=1.2,
                                connectionstyle='arc3,rad=0'), zorder=2)

arr(ax, 0.907, 0.533, 0.930, 0.533)

# ── Legend ─────────────────────────────────────────────────────────────────────
legend = [
    (SEC_CLR,  '#ff9955', 'Security Checkpoint — PII scrub + injection detect'),
    (HITL_CLR, '#64b5f6', 'Approval Gate — Human-in-the-Loop (HITL)'),
    (AGENT_BG, NEON_G,    'LlmAgent Specialist — with MCP tools'),
    (BLOCK_BG, '#ff4444', 'blocked_output — SECURITY_EVENT terminal'),
    (MCP_BG,   NEON_P,    'MCP Server — 5 tools via stdio transport'),
]
for i, (bg_, bdr, lbl) in enumerate(legend):
    lx, ly = 0.013, 0.228 - i * 0.047
    ax.add_patch(FancyBboxPatch((lx, ly - 0.014), 0.021, 0.028,
                                 boxstyle='round,pad=0.003', facecolor=bg_,
                                 edgecolor=bdr, linewidth=1.2,
                                 transform=ax.transAxes, zorder=3))
    ax.text(lx + 0.027, ly, lbl, va='center', color=TEXT_LO, fontsize=7,
            transform=ax.transAxes)

plt.tight_layout(pad=0)
plt.savefig('assets/architecture_diagram.png', dpi=100, bbox_inches='tight',
            facecolor=BG)
plt.close()
print('OK: assets/architecture_diagram.png saved')


# ═══════════════════════════════════════════════════════════════════════════════
# COVER BANNER  1920 × 1080
# ═══════════════════════════════════════════════════════════════════════════════
fig2, ax2 = plt.subplots(figsize=(19.2, 10.8), dpi=100)
fig2.patch.set_facecolor('#04080f')
ax2.set_facecolor('#04080f')
ax2.set_xlim(0, 1); ax2.set_ylim(0, 1); ax2.axis('off')

# Ambient glow (right side)
for r, alp, col in [(0.55, 0.06, NEON_P), (0.40, 0.05, NEON_G), (0.25, 0.04, NEON_B)]:
    ax2.add_patch(Circle((0.80, 0.50), r, color=col, alpha=alp,
                          transform=ax2.transAxes, zorder=1))

# Hex network
hex_pts = [(0.77, 0.76), (0.86, 0.60), (0.68, 0.60),
           (0.77, 0.44), (0.95, 0.76), (0.95, 0.44),
           (0.59, 0.76), (0.59, 0.44)]
hex_clrs = [NEON_G, NEON_B, NEON_P, NEON_G, NEON_B, NEON_P, NEON_G, NEON_B]
for (hx, hy), hc in zip(hex_pts, hex_clrs):
    for sr, sa in [(0.048, 0.10), (0.036, 0.30)]:
        ax2.add_patch(RegularPolygon((hx, hy), 6, radius=sr, color=hc,
                                      alpha=sa, transform=ax2.transAxes, zorder=2))
for i, j in [(0,1),(0,2),(1,3),(2,3),(0,4),(0,5),(1,5),(2,6),(2,7),(3,7)]:
    x1, y1 = hex_pts[i]; x2, y2 = hex_pts[j]
    ax2.plot([x1, x2], [y1, y2], color='#1e3a5f', lw=1.3, alpha=0.5,
             transform=ax2.transAxes, zorder=1)

# Vertical divider
ax2.plot([0.52, 0.52], [0, 1], color='#1e3a5f', lw=1.5, alpha=0.4, transform=ax2.transAxes)

# Title
ax2.text(0.04, 0.730, 'ROUNDSMATE', transform=ax2.transAxes,
         color='#ffffff', fontsize=82, fontweight='bold', va='center',
         fontfamily='monospace')

# Neon underline
ax2.plot([0.04, 0.50], [0.620, 0.620], color=NEON_G, lw=4,
         transform=ax2.transAxes, solid_capstyle='round')

# Subtitle
ax2.text(0.04, 0.558, 'AI Administrative Assistant for Doctors',
         transform=ax2.transAxes, color='#c5cae9', fontsize=26, va='center')

# Tagline
ax2.text(0.04, 0.472, 'Automated  ·  Secure  ·  Intelligent',
         transform=ax2.transAxes, color='#7986cb', fontsize=20,
         va='center', style='italic')

# Feature badges
badges = [
    ('ADK Multi-Agent', NEON_G),
    ('MCP Server', NEON_B),
    ('HITL Approval Gate', NEON_O),
    ('Security Checkpoint', NEON_P),
]
bx = 0.04
for label, clr in badges:
    bw = len(label) * 0.0098 + 0.030
    ax2.add_patch(FancyBboxPatch((bx, 0.348), bw, 0.054,
                                  boxstyle='round,pad=0.006', facecolor='#080e1a',
                                  edgecolor=clr, linewidth=1.8, alpha=0.95,
                                  transform=ax2.transAxes, zorder=3))
    ax2.text(bx + bw / 2, 0.375, label, ha='center', va='center',
             color=clr, fontsize=12, fontweight='bold',
             transform=ax2.transAxes, zorder=4)
    bx += bw + 0.018

# Meta line
ax2.text(0.04, 0.240,
         'Track: Agents for Good  ·  Google ADK 2.0  ·  Gemini 2.5 Flash  ·  Python 3.12',
         transform=ax2.transAxes, color='#546e7a', fontsize=13, va='center')

# Impact quote
ax2.text(0.04, 0.158,
         '"Indian doctors spend 3 hours a day on paperwork. RoundsMate cuts that to 8 minutes."',
         transform=ax2.transAxes, color='#b0bec5', fontsize=15,
         va='center', style='italic')

# Watermark
ax2.text(0.97, 0.038, 'Powered by Google ADK', ha='right', va='bottom',
         color='#263238', fontsize=11, transform=ax2.transAxes, style='italic')

plt.tight_layout(pad=0)
plt.savefig('assets/cover_page_banner.png', dpi=100, bbox_inches='tight',
            facecolor='#04080f')
plt.close()
print('OK: assets/cover_page_banner.png saved')
