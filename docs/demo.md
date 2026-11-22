# Teste rápido do AccessMatch

## Abra a aplicação

Com Docker e Ollama abertos, rode na pasta do projeto:

```sh
make prepare-demo
```

Abra o [catálogo de imóveis](http://localhost:3000).

## Teste a comparação

1. Selecione **Edifício Ipê** e **Residencial Oliveira**. Na barra inferior, clique em **Comparar imóveis**.
2. Marque **Verificar acesso sem degraus**, informe **75 cm** em **Largura livre mínima da passagem** e clique em **Confirmar critérios**. Aguarde os resultados.
3. No card de degraus do Ipê, abra **Ver evidências**. Confira a foto do degrau e o anúncio que declara entrada sem degraus.
4. No card de largura do Oliveira, confira os **78 cm** registrados na vistoria. Altere o mínimo para **80 cm** e clique em **Atualizar comparação**. Confira se o resultado muda de **Atende à medida solicitada** para **Abaixo da medida solicitada**.
5. No Ipê, clique em **Gerar perguntas ao anunciante**. Confira a pergunta sobre outro acesso sem degraus, edite a mensagem e clique em **Copiar mensagem**. Cole em um editor de texto para conferir a cópia.
