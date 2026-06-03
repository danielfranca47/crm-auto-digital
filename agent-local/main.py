"""Ponto de entrada do agent-local — app standalone de geração de leads."""
from __future__ import annotations

import customtkinter as ctk

from app.session import load_session, save_session

APP_TITLE = "Gerador de Leads — AutoDigital"
APP_GEOMETRY = "620x720"


class AgentLocalApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.geometry(APP_GEOMETRY)
        self.resizable(False, False)
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("blue")

        self._current_frame = None
        self._check_session()

    # ── Navegação ──────────────────────────────────────────────────────────────

    def _check_session(self):
        session = load_session()
        if not session:
            self.show_login()
            return

        # Tenta atualizar o status de assinatura em background sem bloquear a UI
        import threading

        def _refresh():
            try:
                from app.auth import check_subscription
                result = check_subscription(session["access_token"])
                session["subscription_status"] = result["subscription_status"]
                save_session(session)
            except Exception:
                pass  # Mantém status em cache se o servidor não estiver acessível
            finally:
                self.after(0, lambda: self._route_after_auth(session))

        threading.Thread(target=_refresh, daemon=True).start()

    def _route_after_auth(self, session: dict):
        if not session.get("onboarding_done"):
            self.show_onboarding(session)
        else:
            self.show_main(session)

    def show_login(self):
        from app.ui.login_screen import LoginScreen
        self._switch(LoginScreen(self, on_login=self._on_auth, on_register=self.show_register))

    def show_register(self):
        from app.ui.register_screen import RegisterScreen
        self._switch(RegisterScreen(self, on_register=self._on_auth, on_login=self.show_login))

    def show_onboarding(self, session: dict):
        from app.ui.onboarding_screen import OnboardingScreen
        self._switch(
            OnboardingScreen(self, session_data=session, on_done=lambda: self.show_main(session))
        )

    def show_main(self, session: dict):
        from app.ui.main_screen import MainScreen
        self._switch(MainScreen(self, session_data=session, on_logout=self.show_login))

    def _on_auth(self, session_data: dict):
        save_session(session_data)
        if not session_data.get("onboarding_done"):
            self.show_onboarding(session_data)
        else:
            self.show_main(session_data)

    def _switch(self, new_frame: ctk.CTkFrame):
        if self._current_frame:
            self._current_frame.destroy()
        self._current_frame = new_frame
        self._current_frame.pack(fill="both", expand=True)


def main():
    app = AgentLocalApp()
    app.mainloop()


if __name__ == "__main__":
    main()
