"use client";
import { useEffect, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { liveFrame } from "./schemas";
import { token } from "./api";
import type { z } from "zod";

export function reconnectDelay(attempt: number): number {
  return Math.min(30_000, 1000 * 2 ** Math.min(attempt, 8));
}
export function useLive() {
  const client = useQueryClient();
  const [frame, setFrame] = useState<z.infer<typeof liveFrame> | null>(null);
  const [connected, setConnected] = useState(false);
  useEffect(() => {
    let socket: WebSocket | undefined,
      timer: ReturnType<typeof setTimeout> | undefined;
    let heartbeat: ReturnType<typeof setInterval> | undefined,
      stopped = false,
      attempt = 0,
      version = 0,
      lastSeen = Date.now();
    const connect = () => {
      if (stopped || !token()) return;
      socket = new WebSocket(
        `${location.protocol === "https:" ? "wss" : "ws"}://${location.host}/api/ws/live`,
      );
      socket.onopen = () => {
        socket?.send(
          JSON.stringify({ token: token(), last_incident_version: version }),
        );
      };
      socket.onmessage = (event) => {
        let payload: unknown;
        try {
          payload = JSON.parse(event.data);
        } catch {
          socket?.close();
          return;
        }
        const result = liveFrame.safeParse(payload);
        if (!result.success) {
          socket?.close();
          return;
        }
        setConnected(true);
        client.setQueryData(["live-connection"], true);
        attempt = 0;
        lastSeen = Date.now();
        version = result.data.incident_version;
        setFrame(result.data);
        client.setQueryData(["live"], result.data);
        if (result.data.incidents.length)
          void client.invalidateQueries({ queryKey: ["incidents"] });
      };
      socket.onclose = (event) => {
        setConnected(false);
        client.setQueryData(["live-connection"], false);
        if (!stopped && event.code !== 1008)
          timer = setTimeout(connect, reconnectDelay(attempt++));
      };
      socket.onerror = () => socket?.close();
    };
    connect();
    heartbeat = setInterval(() => {
      if (Date.now() - lastSeen > 15_000) socket?.close();
    }, 5000);
    return () => {
      stopped = true;
      clearTimeout(timer);
      clearInterval(heartbeat);
      socket?.close();
    };
  }, [client]);
  return { frame, connected };
}
