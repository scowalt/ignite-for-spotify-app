interface SkeletonProps {
  class?: string;
}

export function SkeletonBox(props: SkeletonProps) {
  return (
    <div
      class={`skeleton ${props.class ?? ""}`}
    />
  );
}

export function SkeletonText(props: SkeletonProps) {
  return (
    <span
      class={`skeleton skeleton-text ${props.class ?? "skeleton-line"}`}
    />
  );
}

export function SkeletonCircle(props: SkeletonProps) {
  return (
    <div
      class={`skeleton skeleton-circle ${props.class ?? "skeleton-avatar"}`}
    />
  );
}

export function HeaderAuthSkeleton() {
  return (
    <div class="header-account">
      <SkeletonCircle class="skeleton-avatar" />
      <SkeletonText class="skeleton-header-name" />
      <SkeletonText class="skeleton-header-action" />
    </div>
  );
}

export function UserInfoSkeleton() {
  return (
    <div class="panel user-info-skeleton">
      <SkeletonCircle class="skeleton-user-avatar" />
      <div class="skeleton-user-text">
        <SkeletonText class="skeleton-user-name" />
        <SkeletonText class="skeleton-user-detail" />
      </div>
      <SkeletonText class="skeleton-user-action" />
    </div>
  );
}

export function PlaylistCardSkeleton() {
  return (
    <div class="playlist-card-skeleton">
      <SkeletonBox class="skeleton-playlist-card-art" />
      <div class="skeleton-playlist-text">
        <SkeletonText class="skeleton-playlist-name" />
        <SkeletonText class="skeleton-playlist-count" />
      </div>
    </div>
  );
}

export function PlaylistGridSkeleton() {
  return (
    <div class="playlist-grid-skeleton">
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
    <div class="panel discover-stats">
      <div>
        <SkeletonText class="skeleton-stat-label" />
        <SkeletonText class="skeleton-stat-value" />
      </div>
      <div>
        <SkeletonText class="skeleton-stat-label-wide" />
        <SkeletonText class="skeleton-stat-value" />
      </div>
      <div>
        <SkeletonText class="skeleton-stat-label" />
        <SkeletonText class="skeleton-stat-value-narrow" />
      </div>
    </div>
  );
}

export function AuthSectionSkeleton() {
  return (
    <div class="panel auth-skeleton">
      <SkeletonText class="skeleton-auth-text" />
      <SkeletonBox class="skeleton-auth-button" />
    </div>
  );
}

function TableRowSkeleton() {
  return (
    <tr class="skeleton-results-row">
      <td>
        <SkeletonBox class="skeleton-cell-checkbox" />
      </td>
      <td>
        <SkeletonText class="skeleton-cell-artist" />
      </td>
      <td>
        <SkeletonText class="skeleton-cell-title" />
      </td>
      <td>
        <SkeletonText class="skeleton-cell-album" />
      </td>
      <td>
        <div class="badge-list">
          <SkeletonBox class="skeleton-badge" />
          <SkeletonBox class="skeleton-badge" />
        </div>
      </td>
      <td>
        <SkeletonText class="skeleton-cell-spotify" />
      </td>
    </tr>
  );
}

export function SearchResultsTableSkeleton() {
  return (
    <div class="stack-section">
      <div class="results-header">
        <SkeletonText class="skeleton-results-title" />
        <div class="results-actions">
          <SkeletonText class="skeleton-results-select" />
          <SkeletonText class="skeleton-results-clear" />
        </div>
      </div>
      <div class="panel results-table-wrap">
        <table class="results-table">
          <thead>
            <tr>
              <th class="results-select-column" />
              <th class="results-heading">Artist</th>
              <th class="results-heading">Title</th>
              <th class="results-heading">Album</th>
              <th class="results-heading">Parts</th>
              <th class="results-heading">Spotify</th>
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
    <div class="playlist-item-skeleton">
      <SkeletonBox class="skeleton-playlist-art" />
      <div class="skeleton-playlist-text">
        <SkeletonText class="skeleton-playlist-name" />
        <SkeletonText class="skeleton-playlist-count" />
      </div>
    </div>
  );
}

export function PlaylistSidebarSkeleton() {
  return (
    <div class="playlist-list">
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
    <div class="page">
      { }
      <div>
        <SkeletonText class="skeleton-page-title" />
        <SkeletonText class="skeleton-page-lede" />
      </div>
      { }
      <SkeletonBox class="skeleton-page-block" />
      <SkeletonBox class="skeleton-page-block-tall" />
    </div>
  );
}
