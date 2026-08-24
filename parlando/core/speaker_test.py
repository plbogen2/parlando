"""Unit Tests for Generic Speaker Detection and Scene-Aware Multi-Voice Casting."""

import json
import tempfile
import unittest
from parlando.core.chunker import ChunkType, NarrativeChunker
from parlando.core.speaker import (
    CharacterProfile,
    GenericSpeakerDetector,
    SceneAwareVoiceCaster,
    normalize_character_input,
)


class SpeakerDetectorTest(unittest.TestCase):

    def setUp(self):
        self.chunker = NarrativeChunker()
        self.detector = GenericSpeakerDetector()

    def test_generic_multi_character_attribution(self):
        sample_prose = (
            "The sky above the port was the color of television, tuned to a dead channel.\n\n"
            '"It\'s not like I\'m using," Case said, leaning against the damp neon-lit counter of the Chatsubo. '
            '"My nervous system is burned out. I can\'t jack in."\n\nLinda Lee looked at him through the smoky '
            'violet haze of the bar. "You\'re chasing ghosts, Case. Night City will chew you up and spit out whatever '
            'chrome you have left."\n\n"I have a contact in the Sprawl," he muttered, watching the bartender pour another '
            'draft. "An Ono-Sendai cyberdeck with military-grade icebreakers."\n\n"Be careful," she whispered, touching '
            'the synthetic skin of his jacket. "The corporations own the matrix. They own everything."\n\n'
            '# Chapter 2: The Coffin Racks\n\n'
            'The cheap hotel was a honeycomb of fiberglass capsules stacked six high against the blind brick wall.\n\n'
            '"Ten credits for the night," the clerk rasped, not looking up from his pocket terminal.'
        )

        chunks = self.chunker.chunk_text(sample_prose)
        attributed = self.detector.attribute_chunks(chunks)

        detected_names = set(self.detector.characters.keys())
        self.assertIn("Case", detected_names)
        self.assertIn("Linda Lee", detected_names)
        self.assertIn("The Clerk", detected_names)

        # Verify genders detected
        self.assertEqual(self.detector.characters["Case"].gender, "male")
        self.assertEqual(self.detector.characters["Linda Lee"].gender, "female")

        # Verify scene-aware voice allocation
        voice_map = SceneAwareVoiceCaster.cast_characters(
            self.detector.characters,
            engine_type="gemini",
            primary_narrator_voice="Fenrir"
        )

        self.assertEqual(voice_map["Narrator"], "Fenrir")
        self.assertEqual(voice_map["Case"], "Puck")
        self.assertEqual(voice_map["Linda Lee"], "Aoede")
        # The Clerk is a distinct male character in Ch 2
        self.assertIn(voice_map["The Clerk"], ["Charon", "Oran", "Zephyr", "Puck"])

    def test_predefined_characters_input_normalization(self):
        """Tests that normalize_character_input parses dicts, lists, strings, and files."""
        # 1. Dict with nested dicts
        d1 = {
            "Case": {"gender": "male", "voice": "Charon"},
            "Linda Lee": {"gender": "female", "voice": "Kore", "aliases": ["Linda"]},
        }
        res1 = normalize_character_input(d1)
        self.assertEqual(res1["Case"].gender, "male")
        self.assertEqual(res1["Case"].assigned_voice, "Charon")
        self.assertEqual(res1["Linda Lee"].gender, "female")
        self.assertEqual(res1["Linda Lee"].assigned_voice, "Kore")
        self.assertIn("Linda", res1["Linda Lee"].aliases)

        # 2. Dict with shorthand gender / voice
        d2 = {"Case": "male", "Linda": "Aoede"}
        res2 = normalize_character_input(d2)
        self.assertEqual(res2["Case"].gender, "male")
        self.assertEqual(res2["Linda"].assigned_voice, "Aoede")

        # 3. List of formatted strings
        l1 = ["Case:male:Zephyr", "Linda:female:Leda", "Clerk:m"]
        res3 = normalize_character_input(l1)
        self.assertEqual(res3["Case"].assigned_voice, "Zephyr")
        self.assertEqual(res3["Linda"].assigned_voice, "Leda")
        self.assertEqual(res3["Clerk"].gender, "male")

        # 4. JSON file
        with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as tf:
            json.dump({"Molly": {"gender": "female", "voice": "Aoede"}}, tf)
            tf_path = tf.name

        res4 = normalize_character_input(tf_path)
        self.assertEqual(res4["Molly"].gender, "female")
        self.assertEqual(res4["Molly"].assigned_voice, "Aoede")

    def test_predefined_characters_with_auto_detected_merge(self):
        """User specifies custom voice for Case and Linda Lee; Clerk is auto-detected and given distinct voice."""
        custom_cast = {
            "Case": {"gender": "male", "voice": "Charon"},
            "Linda Lee": {"gender": "female", "voice": "Leda"},
        }
        detector = GenericSpeakerDetector(predefined_characters=custom_cast)

        sample_prose = (
            '"I need out," Case said.\n\n'
            'Linda Lee shook her head. "No one gets out."\n\n'
            '# Chapter 2\n\n'
            '"Pay up," the clerk rasped.'
        )

        chunks = self.chunker.chunk_text(sample_prose)
        detector.attribute_chunks(chunks)

        # Verify predefined were retained and Clerk was auto-detected
        self.assertEqual(detector.characters["Case"].assigned_voice, "Charon")
        self.assertEqual(detector.characters["Linda Lee"].assigned_voice, "Leda")
        self.assertIn("The Clerk", detector.characters)

        voice_map = SceneAwareVoiceCaster.cast_characters(
            detector.characters,
            engine_type="gemini",
            primary_narrator_voice="Fenrir"
        )

        # Predefined voices must be locked in
        self.assertEqual(voice_map["Case"], "Charon")
        self.assertEqual(voice_map["Linda Lee"], "Leda")
        self.assertEqual(voice_map["Narrator"], "Fenrir")
        # Clerk should be assigned an available voice
        self.assertIsNotNone(voice_map.get("The Clerk"))

    def test_scene_aware_conflict_avoidance(self):
        """Characters talking to each other MUST be assigned different voices."""
        chars = {
            "Alice": CharacterProfile(name="Alice", gender="female", line_count=10, interacts_with={"Bob"}),
            "Bob": CharacterProfile(name="Bob", gender="male", line_count=10, interacts_with={"Alice"}),
            "Charlie": CharacterProfile(name="Charlie", gender="male", line_count=5, interacts_with={"David"}),
            "David": CharacterProfile(name="David", gender="male", line_count=5, interacts_with={"Charlie"}),
        }

        voice_map = SceneAwareVoiceCaster.cast_characters(chars, engine_type="gemini")

        # Conversational partners must never share the same voice
        self.assertNotEqual(voice_map["Alice"], voice_map["Bob"])
        self.assertNotEqual(voice_map["Charlie"], voice_map["David"])


if __name__ == "__main__":
    unittest.main()
