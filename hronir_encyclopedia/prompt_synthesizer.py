# hronir_encyclopedia/prompt_synthesizer.py
from typing import Dict, Any

def synthesize_prompt_from_themes(themes: Dict[str, Any], target_position: int, target_variant_id: str) -> str:
    """
    Placeholder function to synthesize an LLM prompt from extracted themes.
    """
    print(f"[Placeholder] Synthesizing prompt for Chapter {target_position} (Variant {target_variant_id}).")
    print(f"[Placeholder] Received themes: {themes}")

    # In a real implementation, this would involve more sophisticated analysis of the 'themes'
    # dictionary and more nuanced prompt engineering. It might also include:
    # - Summaries of previous chapters.
    # - Specific instructions on characters, plot points to continue or introduce.
    # - Negative constraints (e.g., topics to avoid).
    # - Instructions for output format (e.g., Markdown).

    main_theme = themes.get("dominant_theme", "the enigmatic nature of reality")
    keywords = themes.get("keywords", ["scholarly inquiry", "speculative fiction"])
    entities = themes.get("mentioned_entities", [])

    prompt_lines = [
        f"**System Prompt: Hrönir Encyclopedia - Chapter Generation**",
        f"----------------------------------------------------------",
        f"You are a contributor to 'The Hrönir Encyclopedia,' a collaborative work of speculative fiction written in a Borgesian style.",
        f"Your task is to write the content for Chapter {target_position}, designated as Variant {target_variant_id}.",
        "",
        f"**Context from Previous Chapters (Derived Themes):**",
        f"  - Dominant Theme: {main_theme}",
        f"  - Key Concepts/Keywords: {', '.join(keywords)}",
    ]
    if entities:
        prompt_lines.append(f"  - Previously Mentioned Entities: {', '.join(entities)}")

    prompt_lines.extend([
        "",
        f"**Instructions for Chapter {target_position} (Variant {target_variant_id}):**",
        f"  1. **Style & Tone:** Maintain a detached, scholarly, and slightly melancholic tone, characteristic of Borges. Employ intricate sentence structures, paradoxes, and allusions to fictional or real obscure texts.",
        f"  2. **Content Direction:** Weave the established themes and keywords into a new narrative segment. The chapter should explore aspects of philosophical idealism, the nature of knowledge, or the unsettling intrusion of fictional realities into the perceived world.",
        f"  3. **Narrative Structure:** The chapter can be a fragment, an essay, a review of a non-existent book, or a biographical sketch of an imagined scholar. It should feel like one piece of a larger, labyrinthine puzzle.",
        f"  4. **Length:** Approximately 600-800 words.",
        f"  5. **Originality:** While building on established themes, introduce novel elements or perspectives that deepen the mystery and complexity of Hrönir.",
        f"  6. **Output Format:** Plain text or Markdown.",
        "",
        f"Begin writing Chapter {target_position} (Variant {target_variant_id}):"
    ])

    final_prompt = "\n".join(prompt_lines)
    print("[Placeholder] Successfully generated LLM prompt.")
    return final_prompt

if __name__ == '__main__':
    print("--- Testing synthesize_prompt_from_themes ---")
    # Example data similar to what extract_themes_from_chapters might provide
    dummy_themes_data = {
        "dominant_theme": "philosophical_idealism",
        "keywords": ["tlon", "uqbar", "mirrors", "encyclopedias", "reality", "language"],
        "sentiment": "neutral-to-mysterious",
        "mentioned_entities": ["Anglo-American Cyclopaedia", "Uqbar", "Tlön"]
    }
    chapter_pos = 1  # Target next chapter, assuming 00 was the intro
    variant_id = "alpha"

    print(f"\n[Test 1] Generating prompt for Chapter {chapter_pos}, Variant {variant_id}")
    generated_prompt = synthesize_prompt_from_themes(dummy_themes_data, chapter_pos, variant_id)

    print("\n--- Generated Prompt (Test 1) ---")
    print(generated_prompt)
    print("--- End of Prompt (Test 1) ---\n")

    # Test with minimal theme data
    minimal_themes_data = {}
    chapter_pos_2 = 2
    variant_id_2 = "beta_01"
    print(f"\n[Test 2] Generating prompt for Chapter {chapter_pos_2}, Variant {variant_id_2} with minimal themes")
    generated_prompt_2 = synthesize_prompt_from_themes(minimal_themes_data, chapter_pos_2, variant_id_2)

    print("\n--- Generated Prompt (Test 2) ---")
    print(generated_prompt_2)
    print("--- End of Prompt (Test 2) ---")

    print("\n--- End of tests ---")
