# Proof-of-Work Voting

Voting in The Hrönir Encyclopedia is inseparable from contributing new narrative material. Each vote must prove that the voter expanded the story.

## Ato 1: Criação (O Trabalho)
Generate one or more hrönirs and store them using the `store` command. Every stored hrönir references a `prev_uuid` so the narrative chain remains intact.

## Ato 2: Conexão (A Prova)
Create a new entry in `forking_path/yu-tsun.csv` linking a `prev_uuid` to the newly stored hrönir's `uuid`. This row deterministically generates a `fork_uuid` which serves as your proof of work.

## Ato 3: Votação (O Uso da Prova)
Use the `vote` command with the generated `fork_uuid` to choose between competing hrönirs:

```bash
python -m hronir_encyclopedia.cli vote \
  --position 1 \
  --voter <fork_uuid> \
  --winner <uuid> --loser <uuid>
```

The system validates the `fork_uuid` and ensures it has not been used previously at that position. By tying each vote to a real forking path, the encyclopedia grows organically while remaining resistant to spam.
