// src/components/whatsapp/WhatsAppLogin.tsx
import React, { useEffect, useRef, useState } from "react";
import { api } from "@/services/api";

const WhatsAppLogin: React.FC = () => {
  const [qrCode, setQrCode] = useState("");
  const [status, setStatus] = useState<
    "iniciando" | "carregando_qr" | "qr_disponivel" | "logado" | "qr_expirado" | "erro"
  >("iniciando");
  const [logado, setLogado] = useState(false);

  // timers
  const intervalRef = useRef<number | null>(null);
  const timeoutRef = useRef<number | null>(null);

  const clearTimers = () => {
    if (intervalRef.current) {
      clearInterval(intervalRef.current);
      intervalRef.current = null;
    }
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current);
      timeoutRef.current = null;
    }
  };

  useEffect(() => {
    return () => clearTimers(); // cleanup on unmount
  }, []);

  const iniciarVerificacaoLogin = () => {
    // evita múltiplos intervals/timeouts
    clearTimers();

    intervalRef.current = window.setInterval(async () => {
      try {
        const data = await api.whatsapp.verificarLogin({ passive: true });
        if (data?.logado) {
          setLogado(true);
          setStatus("logado");
          clearTimers();
        }
      } catch (err) {
        console.error("Erro ao verificar login:", err);
      }
    }, 2000);

    // expira QR após 2 min
    timeoutRef.current = window.setTimeout(() => {
      if (!logado) {
        setStatus("qr_expirado");
        clearTimers();
      }
    }, 120000);
  };

  const iniciarQR = async () => {
    try {
      setStatus("carregando_qr");
      const data = await api.whatsapp.iniciarQR();
      if (data.status === "qr_disponivel" && data.formato) {
        setQrCode(data.formato);
        setStatus("qr_disponivel");
        iniciarVerificacaoLogin();
      } else if (data.status === "logado") {
        setLogado(true);
        setStatus("logado");
        clearTimers();
      } else {
        setStatus("erro");
      }
    } catch (e) {
      console.error(e);
      setStatus("erro");
    }
  };

  const novoQR = async () => {
    try {
      setStatus("carregando_qr");
      const data = await api.whatsapp.novoQR();
      if (data.status === "qr_disponivel" && data.formato) {
        setQrCode(data.formato);
        setStatus("qr_disponivel");
        iniciarVerificacaoLogin();
      } else {
        setStatus("erro");
      }
    } catch (e) {
      console.error(e);
      setStatus("erro");
    }
  };

  return (
    <div className="flex flex-col items-center p-6 bg-white rounded-lg shadow-lg">
      <h2 className="text-2xl font-bold mb-4">Login WhatsApp</h2>

      {status === "iniciando" && (
        <div>
          <p className="mb-4">Clique para conectar ao WhatsApp</p>
          <button onClick={iniciarQR} className="bg-green-500 text-white px-6 py-2 rounded">
            Conectar WhatsApp
          </button>
        </div>
      )}

      {status === "carregando_qr" && (
        <div className="flex flex-col items-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-green-500"></div>
          <p className="mt-2">Carregando QR Code...</p>
        </div>
      )}

      {status === "qr_disponivel" && !logado && (
        <div className="flex flex-col items-center">
          <p className="mb-4 text-center">Escaneie o QR Code com seu WhatsApp:</p>
          <img
            src={qrCode}
            alt="QR Code WhatsApp"
            className="border-2 border-gray-300 rounded"
            style={{ maxWidth: 300 }}
          />
          <div className="mt-4 text-sm text-gray-600 text-center">
            <p>1. Abra o WhatsApp no celular</p>
            <p>2. Menu → Aparelhos conectados</p>
            <p>3. Escaneie este código</p>
          </div>
          <button onClick={novoQR} className="mt-4 bg-blue-500 text-white px-4 py-2 rounded text-sm">
            Gerar Novo QR Code
          </button>
        </div>
      )}

      {status === "logado" && (
        <div className="flex flex-col items-center text-green-600">
          <div className="text-4xl mb-2">✅</div>
          <p className="text-xl font-semibold">WhatsApp Conectado!</p>
          <p className="text-sm text-gray-600 mt-2">Agora o robô pode enviar as mensagens enfileiradas.</p>
        </div>
      )}

      {status === "qr_expirado" && (
        <div className="flex flex-col items-center text-orange-600">
          <div className="text-4xl mb-2">⏰</div>
          <p className="text-xl font-semibold">QR Code Expirado</p>
          <button onClick={novoQR} className="mt-4 bg-green-500 text-white px-4 py-2 rounded">
            Gerar Novo QR Code
          </button>
        </div>
      )}

      {status === "erro" && (
        <div className="flex flex-col items-center text-red-600">
          <div className="text-4xl mb-2">❌</div>
          <p className="text-xl font-semibold">Erro na Conexão</p>
          <button onClick={iniciarQR} className="mt-4 bg-blue-500 text-white px-4 py-2 rounded">
            Tentar Novamente
          </button>
        </div>
      )}
    </div>
  );
};

export default WhatsAppLogin;
