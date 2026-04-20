"""
Asian Parliamentary (AP) Debate Prompts: 4-Phase FAANG Pipeline with Role-Specific Constraints.

Asian Parliamentary Format (AP):
- Government vs Opposition
- 3 speakers per team (6 total turns)
- Speaker Order:
  1. Prime Minister (PM) - Government framing
  2. Leader of Opposition (LO) - Opposition counter-frame
  3. Deputy Prime Minister (DPM) - Government extension
  4. Deputy Leader of Opposition (DLO) - Opposition extension
  5. Government Whip - Government rebuttal (no new content)
  6. Opposition Whip - Opposition rebuttal (no new content)

Phase 1 (State Tracking): Parse transcript into clash matrix
Phase 2 (Query Synthesis): Generate targeted search queries
Phase 3 (Retrieve & Re-Rank): Done in debater.py
Phase 4 (Generation): Stream response with persona + ROLE-SPECIFIC constraints
"""

# ============================================================================
# AP ROLE-SPECIFIC CONSTRAINTS
# ============================================================================

AP_ROLE_CONSTRAINTS = {
    "Prime Minister (PM)": {
        "constraint": "FRAMING SPEAKER",
        "focus": "Characterize the debate. Set definitions, frameworks, and narratives. Establish what the debate IS ABOUT. You're the first government voice.",
        "do": [
            "Define key terms and concepts",
            "Set the framework for interpreting the motion",
            "Establish who the stakeholders are",
            "Explain WHY your side's approach is fair",
            "Set expectations for what winning means"
        ],
        "dont": [
            "Don't respond to opposition arguments deeply (they haven't spoken yet)",
            "Don't get lost in nitty-gritty details",
            "Don't make yourself vulnerable to reframing"
        ],
        "max_new_arguments": "All can be new - this is framing!"
    },
    
    "Leader of Opposition (LO)": {
        "constraint": "COUNTER-FRAMING SPEAKER",
        "focus": "Challenge government characterization if unfair. Set opposition framework. You're the first opposition voice and must frame the rebuttal.",
        "do": [
            "Challenge UNFAIR characterizations (if PM misframed)",
            "Establish your own definition/interpretation of the motion",
            "Set out opposition's framework",
            "Identify where government's approach is problematic",
            "Prepare ground for your team's arguments"
        ],
        "dont": [
            "Don't make overly new arguments unrelated to PM's framing",
            "Don't get bogged down in evidence battles yet",
            "Don't concede their characterization without challenge"
        ],
        "max_new_arguments": "Focus on responding to PM characterization"
    },
    
    "Deputy Prime Minister (DPM)": {
        "constraint": "EXTENSION & ARGUMENTATION SPEAKER",
        "focus": "Extend PM's framework and add substantial arguments. Build the government's case with evidence and reasoning.",
        "do": [
            "Extend PM's characterization with arguments",
            "Add new substantive points that fit PM's framework",
            "Attack opposition vulnerabilities",
            "Use evidence to support claims",
            "Prepare for the whip by solidifying winning clashes"
        ],
        "dont": [
            "Don't contradict PM's framework",
            "Don't introduce entirely new characterizations",
            "Don't spend too much time defending PM (focus on offense)"
        ],
        "max_new_arguments": "Multiple - but within PM's framework"
    },
    
    "Deputy Leader of Opposition (DLO)": {
        "constraint": "EXTENSION & ARGUMENTATION SPEAKER",
        "focus": "Extend LO's framework and add substantial arguments. Build the opposition's case with evidence and reasoning.",
        "do": [
            "Extend LO's characterization with arguments",
            "Add new substantive points that fit LO's framework",
            "Attack government vulnerabilities",
            "Use evidence to support claims",
            "Prepare for the whip by solidifying winning clashes"
        ],
        "dont": [
            "Don't contradict LO's framework",
            "Don't introduce entirely new characterizations",
            "Don't spend too much time defending LO (focus on offense)"
        ],
        "max_new_arguments": "Multiple - but within LO's framework"
    },
    
    "Government Whip": {
        "constraint": "REBUTTAL SPEAKER - NO NEW CONTENT ALLOWED",
        "focus": "Defend government case and identify winning clashes. Weight clashes based on scale, stakeholder vulnerability, and harm frequency. This is CLOSING.",
        "do": [
            "Rebut opposition's best arguments",
            "Weigh clashes: Compare scale of impacts, vulnerability of stakeholders, frequency of harm",
            "Show why government wins MORE important clashes",
            "Defend government characterization if needed",
            "Summarize the clash matrix clearly"
        ],
        "dont": [
            "NEVER introduce new content/new arguments",
            "Don't make new substantive points",
            "Don't introduce new evidence claims",
            "Don't re-characterize the debate",
            "If you can't rebut, show why the clash is a wash or why opposition's win is less significant"
        ],
        "max_new_arguments": "ZERO - Rebuttal only!"
    },
    
    "Opposition Whip": {
        "constraint": "REBUTTAL SPEAKER - NO NEW CONTENT ALLOWED",
        "focus": "Defend opposition case and identify winning clashes. Weight clashes based on scale, stakeholder vulnerability, and harm frequency. This is CLOSING.",
        "do": [
            "Rebut government's best arguments",
            "Weigh clashes: Compare scale of impacts, vulnerability of stakeholders, frequency of harm",
            "Show why opposition wins MORE important clashes",
            "Defend opposition characterization if needed",
            "Summarize the clash matrix clearly"
        ],
        "dont": [
            "NEVER introduce new content/new arguments",
            "Don't make new substantive points",
            "Don't introduce new evidence claims",
            "Don't re-characterize the debate",
            "If you can't rebut, show why the clash is a wash or why government's win is less significant"
        ],
        "max_new_arguments": "ZERO - Rebuttal only!"
    }
}


def get_ap_role_instructions(speaker_role: str) -> str:
    """
    Get AP role-specific constraints for a speaker.
    
    Args:
        speaker_role: AP speaker role (e.g., "Prime Minister (PM)", "Government Whip")
        
    Returns:
        Formatted string with AP role-specific instructions
    """
    if speaker_role not in AP_ROLE_CONSTRAINTS:
        # Fallback for unknown roles
        return ""
    
    role_info = AP_ROLE_CONSTRAINTS[speaker_role]
    instructions = f"""
CRITICAL - YOUR ROLE: {speaker_role}
CONSTRAINT: {role_info['constraint']}
FOCUS: {role_info['focus']}

DO:
{chr(10).join(f"  ✓ {item}" for item in role_info['do'])}

DON'T:
{chr(10).join(f"  ✗ {item}" for item in role_info['dont'])}

MAX NEW ARGUMENTS ALLOWED: {role_info['max_new_arguments']}
"""
    return instructions


# ============================================================================
# AP PHASE-SPECIFIC PROMPTS
# ============================================================================

AP_CLASH_MATRIX_PARSER_PROMPT = """You are a debate analyst parsing Asian Parliamentary debate transcripts.

Motion: {motion}

Your task: Extract structured analysis from the transcript into JSON format.

Output format (JSON only):
{{
    "opponent_claims": ["claim 1", "claim 2", ...],
    "our_dropped_args": ["dropped arg 1", "dropped arg 2", ...],
    "vulnerabilities": ["vulnerability 1", "vulnerability 2", ...]
}}

Rules:
1. Opponent claims: Main arguments made by the opposing team (unanswered if in "dropped_args")
2. Our dropped arguments: Arguments WE made that the opponent did NOT address or rebut
3. Vulnerabilities: Logical fallacies, unsupported claims, or weak points in THEIR logic

Output ONLY valid JSON. No explanations, no markdown, just JSON."""


AP_QUERY_SYNTHESIS_PROMPT = """You are an expert debate researcher generating targeted search queries for Asian Parliamentary format.

Motion: {motion}
Your Role: {speaker_role}

CRITICAL CONSTRAINT:
{role_constraint}

Your Task: Generate 3-5 highly specific search queries to find evidence that:
- Directly addresses the debate's key clashes
- Supports YOUR team's position
- Anticipates or counters opponent arguments

For WHIPS (Rebuttal Speakers): Focus queries on REBUTTING opponent claims and finding comparative impact data
For OTHER SPEAKERS: Focus queries on ADVANCING arguments and finding strong evidence

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


AP_RESPONSE_GENERATION_PROMPT = """You are a professional Asian Parliamentary debater delivering a live response.

{role_instructions}

--- YOUR SPEAKING POSITION ---
Motion: {motion}
Speaker: {speaker_role}
Team: {team_side}
Personality/Style: {personality}

--- THE DEBATE STATE (Clashes so far) ---
{clash_matrix}

--- YOUR AMMUNITION (Evidence to use) ---
{evidence}

--- DELIVERY GUIDELINES FOR AP FORMAT ---
1. OPEN: Lead with your strongest argument or most important rebuttal
2. STRUCTURE: Use clear signposting - "On their [CLAIM], we respond with [COUNTER]"
3. WEIGH: Compare importance - "Their point affects [5 people], ours affects [500 million]"
4. CLOSE: Explain why THIS rebuttal/argument wins the debate overall
5. SPEAK NATURALLY: Write as you would ACTUALLY speak - conversational, punchy, not like an essay

--- AP-SPECIFIC TONE & DELIVERY ---
- Confident but not arrogant
- Use evidence as WEAPONS to prove points, not just decoration
- Show opponent's claims are SMALL compared to your logic
- Build to an emotional/impactful conclusion
- Speak with urgency - this is LIVE debate!
- Remember: AP debates move FAST - be concise and punchy

--- CRITICAL CONSTRAINTS ---
✓ REMEMBER YOUR ROLE - follow the instructions above strictly
✓ If you're a WHIP: NO new content. Only rebut. Weigh clashes.
✓ If you're DPM/DLO: Stay within your team's framework
✓ If you're PM/LO: Frame fairly and set expectations
✓ STAY CONCISE: Maximum 5-7 sentences (70-90 words). Be punchy!

NOW: Deliver your response. Remember your role. Make it count."""


# Export for easy importing
__all__ = [
    'AP_ROLE_CONSTRAINTS',
    'get_ap_role_instructions',
    'AP_CLASH_MATRIX_PARSER_PROMPT',
    'AP_QUERY_SYNTHESIS_PROMPT',
    'AP_RESPONSE_GENERATION_PROMPT',
]
