import { Dialog } from "@kobalte/core/dialog";
import type { JSX } from "solid-js";

interface DrawerProps {
  isOpen: boolean;
  onOpenChange: (isOpen: boolean) => void;
  title: string;
  triggerLabel: string;
  triggerContent: JSX.Element;
  children: JSX.Element;
}

export function Drawer(props: DrawerProps) {
  return (
    <Dialog
      open={props.isOpen}
      onOpenChange={props.onOpenChange}
      modal
    >
      <Dialog.Trigger
        class="drawer-trigger"
        aria-label={props.triggerLabel}
      >
        {props.triggerContent}
      </Dialog.Trigger>

      <Dialog.Portal>
        <Dialog.Overlay class="drawer-overlay" />
        <Dialog.Content class="drawer">
          <div class="drawer-header">
            <Dialog.Title class="drawer-title">
              {props.title}
            </Dialog.Title>
            <Dialog.CloseButton
              class="drawer-close focus-ring"
              aria-label="Close drawer"
            >
              <svg
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  stroke-linecap="round"
                  stroke-linejoin="round"
                  stroke-width="2"
                  d="M6 18L18 6M6 6l12 12"
                />
              </svg>
            </Dialog.CloseButton>
          </div>

          <div class="drawer-body themed-scrollbar">
            {props.children}
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog>
  );
}
