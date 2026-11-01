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
        class="rounded-lg p-2 transition-colors hover:bg-gray-700 md:hidden"
        aria-label={props.triggerLabel}
      >
        {props.triggerContent}
      </Dialog.Trigger>

      <Dialog.Portal>
        <Dialog.Overlay class="fixed inset-0 z-40 bg-black/50 backdrop-blur-sm md:hidden" />
        <Dialog.Content class="fixed inset-y-0 left-0 z-50 flex w-72 flex-col overflow-hidden bg-gray-800 md:hidden">
          <div class="flex shrink-0 items-center justify-between border-b border-gray-700 p-4">
            <Dialog.Title class="text-lg font-semibold">
              {props.title}
            </Dialog.Title>
            <Dialog.CloseButton
              class="ml-auto rounded-lg p-2 transition-colors hover:bg-gray-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-spotify-green"
              aria-label="Close drawer"
            >
              <svg
                class="h-5 w-5"
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

          <div class="themed-scrollbar min-h-0 flex-1 overflow-y-auto overscroll-contain p-4">
            {props.children}
          </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog>
  );
}
