"""
Tutorial 08: Streaming postprocess pipeline (pattern/replace/filter/json/type).

Run:
  python tutorials/08_postprocess_pipeline.py
"""

from typing import Iterator

from alphora.models.llms.stream_helper import BaseGenerator, GeneratorOutput
from alphora.postprocess.filter import FilterPP
from alphora.postprocess.replace import ReplacePP
from alphora.postprocess.pattern_match import PatternMatcherPP
from alphora.postprocess.json_key_extractor import JsonKeyExtractorPP
from alphora.postprocess.type_mapper import TypeMapperPP
from alphora.postprocess.dynamic_type import DynamicTypePP


class TextGenerator(BaseGenerator[GeneratorOutput]):
    def __init__(self, text: str, content_type: str = "char"):
        super().__init__(content_type=content_type)
        self._text = text

    def generate(self) -> Iterator[GeneratorOutput]:
        for i in range(0, len(self._text), 4):
            chunk = self._text[i:i + 4]
            yield GeneratorOutput(content=chunk, content_type=self.content_type)

    async def agenerate(self) -> Iterator[GeneratorOutput]:
        for out in self.generate():
            yield out


def demo_pattern_pipeline() -> None:
    raw = "Hello <think>internal</think> World!"
    gen = TextGenerator(raw)

    strip_think = PatternMatcherPP(
        bos="<think>",
        eos="</think>",
        output_mode="exclude_matched",
        include_bos=False,
        include_eos=False,
    )
    replace = ReplacePP({"World": "Alphora"})
    filter_pp = FilterPP(filter_chars="!")

    pipeline = strip_think >> replace >> filter_pp
    processed = pipeline(gen)
    result = "".join([o.content for o in processed])

    print("=== Pattern Pipeline ===")
    print("raw:", raw)
    print("out:", result)


def demo_json_extractor() -> None:
    raw_json = '{"answer":"ok","data":{"score":99}}'
    gen = TextGenerator(raw_json)
    extractor = JsonKeyExtractorPP(target_key="data.score", output_mode="target_only")
    processed = extractor(gen)
    result = "".join([o.content for o in processed])

    print("\n=== JsonKeyExtractor ===")
    print("raw:", raw_json)
    print("out:", result)


def demo_type_mapping() -> None:
    raw = "Hi? Great!"
    gen = TextGenerator(raw, content_type="text")
    dyn = DynamicTypePP(char_to_content_type={"?": "question", "!": "exclaim"})
    mapper = TypeMapperPP({"question": "q", "exclaim": "bang"})
    processed = mapper(dyn(gen))

    print("\n=== Type Mapping ===")
    for out in processed:
        print(f"{out.content} -> {out.content_type}")


def main() -> None:
    demo_pattern_pipeline()
    demo_json_extractor()
    demo_type_mapping()


if __name__ == "__main__":
    main()
