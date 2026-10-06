"""vLLM general plugin (2026-10-03, RQ1 own-loop OpenCUA-7B): makes vLLM 0.30s OpenCUAProcessor work under transformers 5.

transformers 5 ProcessorMixin infers a processor sub-processors from the __init__ signature (get_attributes).
vLLM OpenCUAProcessor.__init__(vision_config, tokenizer, **kwargs) yields only ["tokenizer"], so the positional
(image_processor, tokenizer, video_processor) passed on by Qwen2VLProcessor.__init__ are zipped wrongly and
image_processor is never set. Declaring the three Qwen2-VL sub-processors restores the intended assignment.
Loaded only by the OpenCUA vLLM server (PYTHONPATH=$W/opencua_vllm_plugin in ownloop2.sh); $W/env is untouched."""


def register():
    from vllm.model_executor.models import opencua
    P = opencua.OpenCUAProcessor
    if "get_attributes" not in P.__dict__:
        P.get_attributes = classmethod(lambda cls: ["image_processor", "tokenizer", "video_processor"])
