#!/bin/bash

echo "--- Verificando configurações de Git hooks ---"

LOCAL_HOOKS_PATH=$(git config core.hooksPath)
# pre-commit sets core.hooksPath to .git/hooks, so we check against that.
# However, the actual pre-commit hook script is what matters.
# The check for `pre-commit install` success is more important.

echo ""
echo "Configuração local de core.hooksPath (git config core.hooksPath):"
if [ -n "$LOCAL_HOOKS_PATH" ]; then
    echo "  Definido como: $LOCAL_HOOKS_PATH"
    # pre-commit versions >= 2.0.0 set core.hooksPath = .git/hooks
    # and then pre-commit manages the actual .git/hooks/pre-commit script.
    # If it's set to something else, it's a definite conflict.
    if [ "$LOCAL_HOOKS_PATH" != ".git/hooks" ]; then
        echo "  AVISO: core.hooksPath local está definido para um caminho não padrão ('$LOCAL_HOOKS_PATH')."
        echo "  Isso VAI conflitar com 'pre-commit install'."
        echo "  'pre-commit install' tentará definir core.hooksPath para '.git/hooks'."
        read -p "  Deseja remover a configuração local de core.hooksPath (git config --unset core.hooksPath)? (s/N): " answer
        if [[ "$answer" =~ ^[Ss]$ ]]; then
            echo "  Removendo core.hooksPath local..."
            git config --unset core.hooksPath
            if [ $? -eq 0 ]; then
                 echo "  core.hooksPath local removido com sucesso."
            else
                 echo "  FALHA ao remover core.hooksPath local. Por favor, verifique manualmente."
            fi
        else
            echo "  Mantendo core.hooksPath local. 'pre-commit install' provavelmente falhará ou não terá efeito."
        fi
    else
        echo "  Está configurado para '.git/hooks'. Isso é o esperado se pre-commit já foi instalado."
    fi
else
    echo "  Não está definido localmente. 'pre-commit install' poderá configurá-lo."
fi

echo ""
echo "Verificando configuração global de core.hooksPath (git config --global core.hooksPath)..."
GLOBAL_HOOKS_PATH=$(git config --global core.hooksPath 2>/dev/null) # 2>/dev/null to suppress error if not set
if [ -n "$GLOBAL_HOOKS_PATH" ]; then
    echo "  Definido globalmente como: $GLOBAL_HOOKS_PATH"
    echo "  AVISO: Uma configuração global de core.hooksPath pode, às vezes, substituir ou"
    echo "  interferir na configuração que o 'pre-commit install' tenta aplicar localmente."
    echo "  Se 'pre-commit install' falhar ou os hooks não executarem, considere"
    echo "  remover a configuração global com: 'git config --global --unset core.hooksPath'"
    echo "  ou garantir que ela não impeça o pre-commit de funcionar neste repositório."
else
    echo "  Não está definido globalmente. Isso geralmente é bom para o pre-commit operar localmente."
fi

echo ""
echo "--- Tentando instalar/reinstalar pre-commit hooks ---"
if command -v pre-commit &> /dev/null; then
    echo "Executando 'pre-commit install'..."
    pre-commit install
    if [ $? -eq 0 ]; then
        echo "  'pre-commit install' executado com sucesso."
        echo "  Verifique se o arquivo .git/hooks/pre-commit existe e é um script do pre-commit."
        echo "  A configuração local de core.hooksPath deve ser agora '.git/hooks'."
        NEW_LOCAL_HOOKS_PATH=$(git config core.hooksPath)
        echo "  Valor atual de core.hooksPath local: '$NEW_LOCAL_HOOKS_PATH'"

    else
        echo "  FALHA ao executar 'pre-commit install'. Verifique as mensagens de erro."
        echo "  Causas comuns incluem permissões ou um estado inconsistente do repositório Git."
    fi
else
    echo "ERRO: Comando 'pre-commit' não encontrado."
    echo "Por favor, instale pre-commit primeiro (ex: pip install pre-commit ou uv pip install pre-commit)"
    echo "e certifique-se de que está no seu PATH."
fi

echo ""
echo "--- Verificação de hooks concluída ---"
echo "Se os hooks não estiverem funcionando, verifique:"
echo "1. Se '.git/hooks/pre-commit' é um script gerenciado pelo pre-commit."
echo "2. Se 'git config core.hooksPath' está apontando para '.git/hooks'."
echo "3. Se não há configurações globais de Git interferindo."
