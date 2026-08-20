"use client";

import { useEffect } from "react";
import { toast } from "sonner";

import {
  getMe,
  markReminderNotified,
  pendingReminderNotifications,
} from "@/lib/api";

const POLL_INTERVAL_MS = 30_000;

/** Request browser notification permission (best-effort). */
function requestNotificationPermission(): void {
  if (typeof window === "undefined" || !("Notification" in window)) return;
  if (Notification.permission === "default") {
    void Notification.requestPermission();
  }
}

/** Fire a browser notification if permitted (best-effort). */
function showBrowserNotification(title: string): void {
  if (typeof window === "undefined" || !("Notification" in window)) return;
  if (Notification.permission !== "granted") return;
  try {
    new Notification("⏰ 知伴提醒", {
      body: title,
      tag: "zhiban-reminder",
    });
  } catch {
    // Some browsers (esp. mobile) throw when constructing Notification.
  }
}

/**
 * Polls for delivered-but-unseen reminders and alerts the user via both a
 * sonner toast (in-app) and a browser notification (when permitted).
 * Mounted globally; no-op until the user is authenticated.
 */
export function ReminderToast() {
  useEffect(() => {
    let cancelled = false;

    async function poll() {
      const me = await getMe();
      if (!me) return;

      try {
        const reminders = await pendingReminderNotifications();
        for (const reminder of reminders) {
          toast(`⏰ ${reminder.title}`, {
            description: "你设置的提醒到时间了",
            duration: 10000,
          });
          showBrowserNotification(reminder.title);
          // Mark as notified so we don't re-toast on the next poll.
          await markReminderNotified(reminder.id);
        }
      } catch {
        // Polling is best-effort; ignore transient errors.
      }
    }

    // Ask for notification permission once shortly after mount (only when
    // the user is already authenticated).
    const permTimer = setTimeout(() => {
      void getMe().then((me) => {
        if (me) requestNotificationPermission();
      });
    }, 2000);

    const timer = setInterval(() => {
      if (!cancelled) void poll();
    }, POLL_INTERVAL_MS);

    // Poll once shortly after mount.
    const initial = setTimeout(() => {
      if (!cancelled) void poll();
    }, 3000);

    return () => {
      cancelled = true;
      clearInterval(timer);
      clearTimeout(initial);
      clearTimeout(permTimer);
    };
  }, []);

  return null;
}
