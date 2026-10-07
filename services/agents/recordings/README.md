# Recordings

The model's recorded answers for the air-gap agent, one file per model call (`air_gap/<key>.json`), written by
`make record-agents` and read by the replay provider (`LLM_PROVIDER=replay`, the default). They are synthetic: the
data the model saw is the generated demo data. They are valid only for the demo-start state (OQ-139); see
`services/agents/README.md`.
