# Welcome to your Lovable project

## Project info

**URL**: https://lovable.dev/projects/bbee0976-2497-4a1b-be60-10caf33631e4

## How can I edit this code?

There are several ways of editing your application.

**Use Lovable**

Simply visit the [Lovable Project](https://lovable.dev/projects/bbee0976-2497-4a1b-be60-10caf33631e4) and start prompting.

Changes made via Lovable will be committed automatically to this repo.

**Use your preferred IDE**

If you want to work locally using your own IDE, you can clone this repo and push changes. Pushed changes will also be reflected in Lovable.

The only requirement is having Node.js & npm installed - [install with nvm](https://github.com/nvm-sh/nvm#installing-and-updating)

Follow these steps:

```sh
# Step 1: Clone the repository using the project's Git URL.
git clone <YOUR_GIT_URL>

# Step 2: Navigate to the project directory.
cd <YOUR_PROJECT_NAME>

# Step 3: Install the necessary dependencies.
npm i

# Step 4: Start the development server with auto-reloading and an instant preview.
npm run dev
```

**Edit a file directly in GitHub**

- Navigate to the desired file(s).
- Click the "Edit" button (pencil icon) at the top right of the file view.
- Make your changes and commit the changes.

**Use GitHub Codespaces**

- Navigate to the main page of your repository.
- Click on the "Code" button (green button) near the top right.
- Select the "Codespaces" tab.
- Click on "New codespace" to launch a new Codespace environment.
- Edit files directly within the Codespace and commit and push your changes once you're done.

## What technologies are used for this project?

This project is built with:

- Vite
- TypeScript
- React
- shadcn-ui
- Tailwind CSS

## How can I deploy this project?

Simply open [Lovable](https://lovable.dev/projects/bbee0976-2497-4a1b-be60-10caf33631e4) and click on Share -> Publish.

## Can I connect a custom domain to my Lovable project?

Yes, you can!

To connect a domain, navigate to Project > Settings > Domains and click Connect Domain.

Read more here: [Setting up a custom domain](https://docs.lovable.dev/tips-tricks/custom-domain#step-by-step-guide)


# 🌐 Website Template — AutoDigital / Lovable Base  
*(English version below)*  

---

## 🇧🇷 Sobre este projeto

Este diretório (`/website`) contém **o modelo base de website** utilizado em projetos AutoDigital.  
Ele foi **gerado originalmente via [Lovable.dev](https://lovable.dev)** e depois integrado ao repositório principal para servir como **template reutilizável**.

⚠️ **Importante:**  
Este website é **apenas um modelo de referência** — não deve conter domínios de produção, formulários conectados ou dados reais.  
Versões personalizadas para clientes devem ser criadas em **branches exclusivas**, por exemplo:

client/danielfranca
client/imobiliaria-lisboa
client/spa-porto


Essas ramificações podem:
- Personalizar cores, textos e imagens.
- Conectar formulários reais ao backend.
- Configurar domínios (ex: `https://danielfranca.pt`).

---

## 🧭 Estrutura e tecnologias

Este template foi criado com:

- **Vite** (ferramenta de build e preview)
- **React + TypeScript**
- **shadcn/ui** (componentes de interface)
- **Tailwind CSS** (estilização)
- **Lovable.dev** (gerador visual e AI de interface)

---

## 🛠️ Como editar este website

### 🔹 Opção 1 — Usar o Lovable (recomendado para design visual)
Acesse o projeto diretamente:
👉 [Lovable Project Dashboard](https://lovable.dev/projects/bbee0976-2497-4a1b-be60-10caf33631e4)

Alterações feitas no Lovable são automaticamente **enviadas para este repositório**.

---

### 🔹 Opção 2 — Editar localmente no VS Code

Requisitos:
- [Node.js + npm](https://github.com/nvm-sh/nvm#installing-and-updating)

Passos:

```bash
# 1. Clonar o repositório principal
git clone https://github.com/danielfranca47/crm-auto-digital.git

# 2. Entrar na pasta do website
cd crm-auto-digital/website

# 3. Instalar dependências
npm install

# 4. Rodar localmente (porta 5175 por padrão)
npm run dev


O site ficará disponível em:
👉 http://localhost:5175/

🔹 Opção 3 — Editar direto pelo GitHub

Abra o arquivo desejado.

Clique no ✏️ (ícone de edição).

Faça as mudanças e commit.

🔹 Opção 4 — GitHub Codespaces (ambiente online)

No repositório, clique em Code > Codespaces > New Codespace.

O ambiente será aberto online com VS Code completo.

🚀 Publicação (Deploy)

O deploy pode ser feito:

Pelo painel do Lovable → botão Share → Publish.

Ou integrando manualmente com um servidor (HostGator, Netlify, Vercel etc).

Para domínios personalizados:

Vá em Project > Settings > Domains > Connect Domain

Guia completa: Custom Domain Setup

📚 Boas práticas para desenvolvedores

Não incluir dados de produção neste template.

Evitar commits de .env ou chaves privadas.

Personalizações reais (ex: formulários, autoresponder, integração CRM) devem ser feitas apenas em branches client/*.

Sincronizar periodicamente com a branch main para herdar melhorias no core.

🇬🇧 English version — Website Template (Lovable Base)

This /website directory contains the base website template used by AutoDigital projects.
It was originally generated through Lovable.dev
 and later integrated into the main repository as a reusable reference.

⚠️ Important:
This is only a reference template — it must not include production domains, live forms, or private data.
Customized websites for clients should live in dedicated branches, for example:

client/danielfranca
client/imobiliaria-lisboa
client/spa-porto


Those branches can:

Adjust design, texts, and images.

Connect forms to real backend endpoints.

Configure real production domains.

🧭 Stack and Tools

Built with:

Vite

React + TypeScript

shadcn/ui

Tailwind CSS

Lovable.dev (AI + visual UI builder)

🧩 Editing Methods
Option 1 — via Lovable

👉 Project link

Changes sync automatically to GitHub.

Option 2 — Locally in your IDE
git clone https://github.com/danielfranca47/crm-auto-digital.git
cd crm-auto-digital/website
npm install
npm run dev


Preview: http://localhost:5175

Option 3 — Directly in GitHub

Edit files in-browser and commit changes.

Option 4 — GitHub Codespaces

Launch a Codespace from the repository and edit online.

🌍 Deployment

You can deploy directly from Lovable (“Share → Publish”) or manually to any hosting service.

For custom domains:
Project → Settings → Domains → Connect Domain
Guide: Lovable Docs - Custom Domain

🧠 Developer Notes

Keep this as a neutral template (no production data).

Never commit real .env or credentials.

Use client/* branches for real deployments.

Regularly merge updates from main to client branches.

✳️ Author: Daniel França — AutoDigital / CRM System
📁 Repository: crm-auto-digital