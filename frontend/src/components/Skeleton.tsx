interface SkeletonProps {
  class?: string;
}

export function SkeletonBox(props: SkeletonProps) {
  return (
    <div
      class={`bg-gray-700 animate-pulse rounded ${props.class ?? ""}`}
    />
  );
}

export function SkeletonText(props: SkeletonProps) {
  return (
    <span
      class={`inline-block bg-gray-700 animate-pulse rounded ${props.class ?? "h-4 w-24"}`}
    />
  );
}

export function SkeletonCircle(props: SkeletonProps) {
  return (
    <div
      class={`bg-gray-700 animate-pulse rounded-full ${props.class ?? "w-8 h-8"}`}
    />
  );
}

export function HeaderAuthSkeleton() {
  return (
    <div class="flex items-center gap-2">
      <SkeletonCircle class="w-8 h-8" />
      <SkeletonText class="h-4 w-24" />
      <SkeletonText class="h-4 w-12" />
    </div>
  );
}

export function UserInfoSkeleton() {
  return (
    <div class="flex items-center gap-4 bg-gray-800 rounded-lg p-4">
      <SkeletonCircle class="w-10 h-10" />
      <div class="flex flex-col gap-1">
        <SkeletonText class="h-4 w-32" />
        <SkeletonText class="h-3 w-40" />
      </div>
      <SkeletonText class="ml-auto h-4 w-14" />
    </div>
  );
}

export function PlaylistCardSkeleton() {
  return (
    <div class="flex items-center gap-3 p-3 rounded-lg border border-gray-700">
      <SkeletonBox class="w-12 h-12" />
      <div class="flex-1 min-w-0 flex flex-col gap-1">
        <SkeletonText class="h-4 w-3/4" />
        <SkeletonText class="h-3 w-16" />
      </div>
    </div>
  );
}

export function PlaylistGridSkeleton() {
  return (
    <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
      <PlaylistCardSkeleton />
      <PlaylistCardSkeleton />
      <PlaylistCardSkeleton />
      <PlaylistCardSkeleton />
      <PlaylistCardSkeleton />
      <PlaylistCardSkeleton />
    </div>
  );
}

export function StatsSkeleton() {
  return (
    <div class="bg-gray-800 rounded-lg p-4 flex gap-8">
      <div>
        <SkeletonText class="h-3 w-16 block mb-1" />
        <SkeletonText class="h-8 w-20" />
      </div>
      <div>
        <SkeletonText class="h-3 w-24 block mb-1" />
        <SkeletonText class="h-8 w-20" />
      </div>
      <div>
        <SkeletonText class="h-3 w-16 block mb-1" />
        <SkeletonText class="h-8 w-16" />
      </div>
    </div>
  );
}

export function AuthSectionSkeleton() {
  return (
    <div class="bg-gray-800 rounded-lg p-6 flex flex-col items-center justify-center">
      <SkeletonText class="h-4 w-64 mb-4" />
      <SkeletonBox class="h-10 w-40 rounded-full" />
    </div>
  );
}

function TableRowSkeleton() {
  return (
    <tr class="border-t border-gray-700">
      <td class="px-4 py-2">
        <SkeletonBox class="w-4 h-4 rounded" />
      </td>
      <td class="px-4 py-2">
        <SkeletonText class="h-4 w-24" />
      </td>
      <td class="px-4 py-2">
        <SkeletonText class="h-4 w-32" />
      </td>
      <td class="px-4 py-2">
        <SkeletonText class="h-4 w-28" />
      </td>
      <td class="px-4 py-2">
        <div class="flex gap-1">
          <SkeletonBox class="w-5 h-5 rounded" />
          <SkeletonBox class="w-5 h-5 rounded" />
        </div>
      </td>
      <td class="px-4 py-2">
        <SkeletonText class="h-4 w-4" />
      </td>
    </tr>
  );
}

export function SearchResultsTableSkeleton() {
  return (
    <div class="space-y-4">
      <div class="flex justify-between items-center">
        <SkeletonText class="h-6 w-32" />
        <div class="flex gap-2">
          <SkeletonText class="h-4 w-16" />
          <SkeletonText class="h-4 w-12" />
        </div>
      </div>
      <div class="bg-gray-800 rounded-lg overflow-hidden">
        <table class="w-full">
          <thead class="bg-gray-700">
            <tr>
              <th class="w-8 px-4 py-2" />
              <th class="text-left px-4 py-2">Artist</th>
              <th class="text-left px-4 py-2">Title</th>
              <th class="text-left px-4 py-2">Album</th>
              <th class="text-left px-4 py-2">Parts</th>
              <th class="text-left px-4 py-2">Spotify</th>
            </tr>
          </thead>
          <tbody>
            <TableRowSkeleton />
            <TableRowSkeleton />
            <TableRowSkeleton />
            <TableRowSkeleton />
            <TableRowSkeleton />
            <TableRowSkeleton />
            <TableRowSkeleton />
            <TableRowSkeleton />
          </tbody>
        </table>
      </div>
    </div>
  );
}

export function PlaylistItemSkeleton() {
  return (
    <div class="flex items-center gap-3 p-2">
      <SkeletonBox class="w-10 h-10 rounded shrink-0" />
      <div class="flex-1 min-w-0 flex flex-col gap-1">
        <SkeletonText class="h-4 w-3/4" />
        <SkeletonText class="h-3 w-16" />
      </div>
    </div>
  );
}

export function PlaylistSidebarSkeleton() {
  return (
    <div class="space-y-1">
      <PlaylistItemSkeleton />
      <PlaylistItemSkeleton />
      <PlaylistItemSkeleton />
      <PlaylistItemSkeleton />
      <PlaylistItemSkeleton />
      <PlaylistItemSkeleton />
      <PlaylistItemSkeleton />
      <PlaylistItemSkeleton />
    </div>
  );
}

export function PageSkeleton() {
  return (
    <div class="space-y-6">
      { }
      <div>
        <SkeletonText class="h-8 w-48 block mb-2" />
        <SkeletonText class="h-4 w-96" />
      </div>
      { }
      <SkeletonBox class="h-32 w-full" />
      <SkeletonBox class="h-64 w-full" />
    </div>
  );
}
