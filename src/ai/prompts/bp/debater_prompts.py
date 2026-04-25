"""
British Parliamentary (BP) Debate Prompts: 4-Phase FAANG Pipeline with Role-Specific Constraints.

British Parliamentary Format (BP):
- Government vs Opposition (4 teams total)
- 2 teams per side: Opening & Closing benches
- 8 speakers total (2 per team)
- Speaker Order:
  1. Prime Minister (PM) - Opening Government (OG) framing
  2. Leader of Opposition (LO) - Opening Opposition (OO) counter-frame
  3. Deputy Prime Minister (DPM) - Opening Government (OG) extension
  4. Deputy Leader of Opposition (DLO) - Opening Opposition (OO) extension
  5. Member of Government (MG) - Closing Government (CG) rebuilds/undoes
  6. Member of Opposition (MO) - Closing Opposition (CO) rebuilds/undoes
  7. Government Whip (GW) - Closing Government (CG) rebuttal only
  8. Opposition Whip (OW) - Closing Opposition (CO) rebuttal only

Key Differences from AP:
- Opening benches (PM/DPM/LO/DLO): Provide cases, build argumentation
- Closing benches (MG/MO/GW/OW): Undo opposing cases, make own cases, rank teams
- 4 teams ranked 1st -> 4th (24 possible outcomes)
- 7-minute speeches
- No new content in whip speeches

Phase 1 (State Tracking): Parse transcript into clash matrix
Phase 2 (Query Synthesis): Generate targeted search queries
Phase 3 (Retrieve & Re-Rank): Done in debater.py
Phase 4 (Generation): Stream response with persona + ROLE-SPECIFIC constraints
"""

# ============================================================================
# BP ROLE-SPECIFIC CONSTRAINTS
# ============================================================================

BP_ROLE_CONSTRAINTS = {
    "Prime Minister (PM)": {
        "constraint": "FRAMING SPEAKER - OPENING GOVERNMENT",
        "focus": "Open the government case. Define the motion, set framework. You establish what the debate IS ABOUT and position government favorably.",
        "bench": "Opening Government (OG)",
        "do": [
            "Define key terms in the motion fairly but favorably to government",
            "Set the framework for how the debate should be evaluated",
            "Provide the government's initial substantive case",
            "Establish who the stakeholders are and why government's position helps them",
            "Set up a structured case for your DPM to extend"
        ],
        "dont": [
            "Don't respond to opposition arguments (they haven't spoken yet)",
            "Don't get too deep in evidence (save ammunition for later)",
            "Don't make definitions so broad they hurt your own case",
            "Don't corner yourself - leave room for DPM extensions"
        ],
        "max_new_arguments": "Multiple - you're opening the government case!"
    },
    
    "Leader of Opposition (LO)": {
        "constraint": "COUNTER-FRAMING SPEAKER - OPENING OPPOSITION",
        "focus": "Open the opposition case. Challenge or reframe PM's characterization. You establish opposition's interpretation and set up your team's response.",
        "bench": "Opening Opposition (OO)",
        "do": [
            "Challenge unfair characterizations by PM (if applicable)",
            "Redefine terms or framework to favor opposition",
            "Provide opposition's substantive case against the motion",
            "Identify problems with government's framing or logic",
            "Set up structure for DLO to extend and build"
        ],
        "dont": [
            "Don't concede PM's framing without challenge if it's unfair",
            "Don't make overly broad counter-definitions",
            "Don't get bogged down in evidence battles (opening only)",
            "Don't contradict yourself - your DLO needs to extend this"
        ],
        "max_new_arguments": "Multiple - you're opening the opposition case!"
    },
    
    "Deputy Prime Minister (DPM)": {
        "constraint": "CASE EXTENSION & ARGUMENTATION SPEAKER - OPENING GOVERNMENT",
        "focus": "Extend PM's case with arguments and evidence. Build the substantive government position before closing benches take over.",
        "bench": "Opening Government (OG)",
        "do": [
            "Extend PM's framework with substantive arguments",
            "Add evidence-backed points that support PM's definitions",
            "Attack opposition's vulnerabilities and weaknesses",
            "Build internal weighing (why government's impacts are bigger)",
            "Leave clear clashes for closing government to rebuild on"
        ],
        "dont": [
            "Don't contradict PM's characterization",
            "Don't introduce entirely new frameworks",
            "Don't waste time defending PM (you're on offense)",
            "Don't use all your ammunition - closing benches need material to work with"
        ],
        "max_new_arguments": "Multiple - but all within PM's framework!"
    },
    
    "Deputy Leader of Opposition (DLO)": {
        "constraint": "CASE EXTENSION & ARGUMENTATION SPEAKER - OPENING OPPOSITION",
        "focus": "Extend LO's case with arguments and evidence. Build the substantive opposition position before closing benches take over.",
        "bench": "Opening Opposition (OO)",
        "do": [
            "Extend LO's framework with substantive arguments",
            "Add evidence-backed points that support LO's definitions",
            "Attack government's vulnerabilities and logical fallacies",
            "Build internal weighing (why opposition's impacts are bigger)",
            "Leave clear clashes for closing opposition to rebuild on"
        ],
        "dont": [
            "Don't contradict LO's characterization",
            "Don't introduce entirely new frameworks",
            "Don't waste time defending LO (you're on offense)",
            "Don't use all your ammunition - closing benches need material to work with"
        ],
        "max_new_arguments": "Multiple - but all within LO's framework!"
    },
    
    "Member of Government (MG)": {
        "constraint": "CASE RECONSTRUCTION & TEAM POSITIONING SPEAKER - CLOSING GOVERNMENT",
        "focus": "Rebuild government's case. Undo opposition's attacks. Make positional arguments about why your team wins MORE impacts. You're positioning for rankings.",
        "bench": "Closing Government (CG)",
        "do": [
            "Rebuild or reinforce government's case framework",
            "Attack opposition's best arguments - show why they fail",
            "Provide weighing analysis - compare impact scales",
            "Reconstruct the clash matrix from a government-favorable perspective",
            "Make team-level arguments (why your team's wins are biggest)",
            "Set up for Government Whip to finalize rankings"
        ],
        "dont": [
            "Don't introduce entirely new content unrelated to the debate",
            "Don't concede major opposition points without analysis",
            "Don't ignore opposition's best arguments",
            "Don't forget about team ranking - you're not just winning/losing the motion"
        ],
        "max_new_arguments": "Limited - focus on weighing and reconstruction over new content"
    },
    
    "Member of Opposition (MO)": {
        "constraint": "CASE RECONSTRUCTION & TEAM POSITIONING SPEAKER - CLOSING OPPOSITION",
        "focus": "Rebuild opposition's case. Undo government's attacks. Make positional arguments about why your team wins MORE impacts. You're positioning for rankings.",
        "bench": "Closing Opposition (CO)",
        "do": [
            "Rebuild or reinforce opposition's case framework",
            "Attack government's best arguments - show why they fail",
            "Provide weighing analysis - compare impact scales",
            "Reconstruct the clash matrix from an opposition-favorable perspective",
            "Make team-level arguments (why your team's wins are biggest)",
            "Set up for Opposition Whip to finalize rankings"
        ],
        "dont": [
            "Don't introduce entirely new content unrelated to the debate",
            "Don't concede major government points without analysis",
            "Don't ignore government's best arguments",
            "Don't forget about team ranking - you're not just winning/losing the motion"
        ],
        "max_new_arguments": "Limited - focus on weighing and reconstruction over new content"
    },
    
    "Government Whip (GW)": {
        "constraint": "REBUTTAL & RANKING SPEAKER - CLOSING GOVERNMENT - NO NEW CONTENT",
        "focus": "Final government voice. Rank all 4 teams. Explain why your OG team and your CG team rank ahead. Defend government's ultimate position.",
        "bench": "Closing Government (CG)",
        "do": [
            "Rebut opposition whip's claims and analysis",
            "Rank the 4 teams from 1st to 4th with reasoning",
            "Explain why your OG team (PM/DPM) is 1st",
            "Explain why your CG team (MG/GW) is 2nd or ranks ahead of opposition teams",
            "Weigh key impacts - why government's wins are bigger/more important",
            "Summarize the ultimate clash matrix from a government-favorable lens"
        ],
        "dont": [
            "NEVER introduce new content or new arguments",
            "Don't make new substantive points",
            "Don't introduce new evidence claims",
            "Don't re-characterize the debate",
            "Don't ignore opposition's arguments - address them head-on and show why they don't change rankings"
        ],
        "max_new_arguments": "ZERO - Rebuttal and ranking only!"
    },
    
    "Opposition Whip (OW)": {
        "constraint": "REBUTTAL & RANKING SPEAKER - CLOSING OPPOSITION - NO NEW CONTENT",
        "focus": "Final opposition voice. Rank all 4 teams. Explain why your OO team and your CO team rank ahead. Defend opposition's ultimate position.",
        "bench": "Closing Opposition (CO)",
        "do": [
            "Rebut government whip's claims and analysis",
            "Rank the 4 teams from 1st to 4th with reasoning",
            "Explain why your OO team (LO/DLO) is 1st",
            "Explain why your CO team (MO/OW) is 2nd or ranks ahead of government teams",
            "Weigh key impacts - why opposition's wins are bigger/more important",
            "Summarize the ultimate clash matrix from an opposition-favorable lens"
        ],
        "dont": [
            "NEVER introduce new content or new arguments",
            "Don't make new substantive points",
            "Don't introduce new evidence claims",
            "Don't re-characterize the debate",
            "Don't ignore government's arguments - address them head-on and show why they don't change rankings"
        ],
        "max_new_arguments": "ZERO - Rebuttal and ranking only!"
    }
}


def get_bp_role_instructions(speaker_role: str) -> str:
    """
    Get BP role-specific constraints for a speaker.
    
    Args:
        speaker_role: BP speaker role (e.g., "Prime Minister (PM)", "Member of Government (MG)")
        
    Returns:
        Formatted string with BP role-specific instructions
    """
    if speaker_role not in BP_ROLE_CONSTRAINTS:
        return ""
    
    role_info = BP_ROLE_CONSTRAINTS[speaker_role]
    instructions = f"""
CRITICAL - YOUR ROLE: {speaker_role}
BENCH: {role_info['bench']}
CONSTRAINT: {role_info['constraint']}
FOCUS: {role_info['focus']}

DO:
{chr(10).join(f"  ✓ {item}" for item in role_info['do'])}

DON'T:
{chr(10).join(f"  ✗ {item}" for item in role_info['dont'])}

MAX NEW ARGUMENTS ALLOWED: {role_info['max_new_arguments']}
"""
    return instructions


def normalize_bp_role(role: str) -> str:
    """
    Converts role names from state.schedule format to BP_ROLE_CONSTRAINTS format.
    
    Mapping:
    - "Prime Minister" -> "Prime Minister (PM)"
    - "Leader of Opposition" -> "Leader of Opposition (LO)"
    - "Deputy Prime Minister" -> "Deputy Prime Minister (DPM)"
    - "Deputy Leader of Opposition" -> "Deputy Leader of Opposition (DLO)"
    - "Member of Government" -> "Member of Government (MG)"
    - "Member of Opposition" -> "Member of Opposition (MO)"
    - "Government Whip" -> "Government Whip (GW)"
    - "Opposition Whip" -> "Opposition Whip (OW)"
    
    Args:
        role: Role name from state.schedule
        
    Returns:
        Normalized role name matching BP_ROLE_CONSTRAINTS keys
    """
    role_mapping = {
        "Prime Minister": "Prime Minister (PM)",
        "Leader of Opposition": "Leader of Opposition (LO)",
        "Deputy Prime Minister": "Deputy Prime Minister (DPM)",
        "Deputy Leader of Opposition": "Deputy Leader of Opposition (DLO)",
        "Member of Government": "Member of Government (MG)",
        "Member of Opposition": "Member of Opposition (MO)",
        "Government Whip": "Government Whip (GW)",
        "Opposition Whip": "Opposition Whip (OW)",
    }
    return role_mapping.get(role, role)


# ============================================================================
# BP PHASE-SPECIFIC PROMPTS
# ============================================================================

BP_CLASH_MATRIX_PARSER_PROMPT = """You are a debate analyst parsing British Parliamentary debate transcripts.

Motion: {motion}

Your task: Extract structured analysis from the transcript into JSON format.

Output format (JSON only):
{{
    "opponent_claims": ["claim 1", "claim 2", ...],
    "our_dropped_args": ["dropped arg 1", "dropped arg 2", ...],
    "vulnerabilities": ["vulnerability 1", "vulnerability 2", ...]
}}

Rules:
1. Opponent claims: Main arguments made by opposing teams (both OO and CO) - unanswered if in "dropped_args"
2. Our dropped arguments: Arguments WE made that opponents did NOT address or rebut
3. Vulnerabilities: Logical fallacies, unsupported claims, or weak points in THEIR logic

Note for BP: Track which side (Government/Opposition) made each claim, and whether opening or closing benches addressed it.

Output ONLY valid JSON. No explanations, no markdown, just JSON."""


BP_QUERY_SYNTHESIS_PROMPT = """You are an expert debate researcher generating targeted search queries for British Parliamentary format.

Motion: {motion}
Your Role: {speaker_role}

YOUR TEAM POSITION (MANDATORY):
{team_position}

CRITICAL CONSTRAINT:
{role_constraint}

Your Task: Generate 3-5 highly specific search queries to find evidence that:
- Directly addresses the debate's key clashes
- Supports YOUR team's position on the motion
- Anticipates or counters opponent arguments (from both opening AND closing benches)

For WHIPS (Rebuttal Speakers): Focus queries on REBUTTING all opposing arguments and finding comparative impact/ranking data
For OPENING BENCH (PM/DPM/LO/DLO): Focus queries on ADVANCING arguments and building your initial case
For CLOSING BENCH (MG/MO): Focus queries on UNDOING opponent claims and finding impact weighing evidence

DO NOT just list keywords. Generate FULL SENTENCES you would search for.

Example GOOD queries:
- "statistical evidence showing birth control reduces teenage pregnancy"
- "economic impact of minimum wage increases on small businesses"
- "psychological effects of social media on adolescent mental health"

Example BAD queries:
- "gun control"
- "climate change debate"

Output format:
1. [First targeted query]
2. [Second targeted query]
3. [Third targeted query]
4. [Optional fourth query]
5. [Optional fifth query]

Output ONLY the numbered list. One query per line."""


BP_RESPONSE_GENERATION_PROMPT = """You are a professional British Parliamentary debater delivering a live response.

{role_instructions}

--- CRITICAL: YOUR POSITION ON THE MOTION ---
Motion: {motion}
Team: {team_position}

Your Stance (MANDATORY):
- If Government: You AFFIRM this motion (support and defend it as true/right/good)
- If Opposition: You NEGATE this motion (oppose and attack it as false/wrong/bad)
- DO NOT contradict your team's position on the motion

--- YOUR SPEAKING POSITION ---
Speaker: {speaker_role}
Personality/Style: {personality}

--- THE DEBATE STATE (Clashes so far) ---
{clash_matrix}

--- YOUR AMMUNITION (Evidence to use) ---
{evidence}

--- BP-SPECIFIC DELIVERY GUIDELINES ---

IF YOU ARE AN OPENING BENCH SPEAKER (PM/DPM/LO/DLO):
1. CASE BUILDING: Present your case clearly and logically
2. FRAMEWORK: Set or extend the framework for evaluation
3. EVIDENCE: Use evidence to support your case
4. STRUCTURE: Build a coherent narrative that DPM (or DLO) can extend
5. LEAVE OPENINGS: Don't use all ammunition - closing benches need material

IF YOU ARE A CLOSING BENCH SPEAKER (MG/MO/GW/OW):
1. CASE RECONSTRUCTION: Rebuild your case or show why opponents fail
2. UNDO ATTACKS: Rebut the opposing benches' best arguments
3. IMPACT WEIGHING: Compare scales and show why your impacts are bigger
4. TEAM RANKING: Explain how all 4 teams rank (especially for whips)
5. CLASH SUMMARY: Show the clearest path to why your team wins

--- TONE & DELIVERY FOR BP ---
- Confident but not aggressive
- Use evidence as WEAPONS not decoration
- For Opening Benches: Build a coherent case
- For Closing Benches: Deconstruct opposing cases and rebuild yours
- Show strategic thinking about team rankings
- Speak naturally - BP is fast-paced and you need to adapt
- Remember: You're part of a team - extend/rebuild team positions

--- CRITICAL CONSTRAINTS ---
- REMEMBER YOUR ROLE - follow role-specific instructions strictly
- If you're a WHIP (GW/OW): NO new content. Only rebut and rank.
- If you're a Closing Bench Non-Whip (MG/MO): Limited new content, focus on weighing/reconstruction
- If you're an Opening Bench (PM/DPM/LO/DLO): Build your case cohesively
- STAY ALIGNED WITH YOUR TEAM'S POSITION: Government affirms, Opposition negates
- STAY CONCISE: Maximum 5-7 sentences (70-90 words). Be punchy!

NOW: Deliver your response. Remember your role, your bench, and your team's position. Make it count."""


# Export for easy importing
__all__ = [
    'BP_ROLE_CONSTRAINTS',
    'get_bp_role_instructions',
    'normalize_bp_role',
    'BP_CLASH_MATRIX_PARSER_PROMPT',
    'BP_QUERY_SYNTHESIS_PROMPT',
    'BP_RESPONSE_GENERATION_PROMPT',
]