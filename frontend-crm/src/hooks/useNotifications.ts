import { useMemo } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/services/api";

export function useNotifications() {
  const queryClient = useQueryClient();

  const { data: notifications = [] } = useQuery({
    queryKey: ["notifications-unread"],
    queryFn: () => api.notifications.getUnread(),
    refetchInterval: 15_000,
  });

  const markReadMutation = useMutation({
    mutationFn: (id: number) => api.notifications.markRead(id),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["notifications-unread"] }),
  });

  const markAllReadMutation = useMutation({
    mutationFn: () => api.notifications.markAllRead(),
    onSuccess: () =>
      queryClient.invalidateQueries({ queryKey: ["notifications-unread"] }),
  });

  /** Set de lead IDs (string) que têm notificações não lidas. */
  const notifiedLeadIds = useMemo(
    () =>
      new Set(
        notifications
          .filter((n) => n.lead_id !== null)
          .map((n) => String(n.lead_id))
      ),
    [notifications]
  );

  return {
    notifications,
    notifiedLeadIds,
    markRead: markReadMutation.mutate,
    markAllRead: markAllReadMutation.mutate,
  };
}
