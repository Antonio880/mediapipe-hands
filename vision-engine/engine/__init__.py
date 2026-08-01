"""Motor de visão computacional: captura, detecção plugável, tracking e eventos.

Este pacote nunca importa nada de `modules/`. Ele define o contrato
(engine.types) e a infraestrutura genérica — qualquer aplicação (face,
contagem de fluxo, EPI) é um plugin que implementa os Protocols de
engine.pipeline (Detector, Enricher, RuleSet).
"""
