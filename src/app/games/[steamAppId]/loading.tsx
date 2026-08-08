import { Skeleton } from "@/components/ui/skeleton";

export default function GameDetailLoading() {
  return (
    <div className="gp-page py-4" aria-label="Loading game details">
      <Skeleton className="aspect-[16/6] w-full rounded-[1.6rem]" />
      <div className="mt-7 grid gap-4 md:grid-cols-[1fr_360px]">
        <div>
          <Skeleton className="h-11 w-2/3" />
          <Skeleton className="mt-4 h-5 w-full max-w-xl" />
          <Skeleton className="mt-2 h-5 w-4/5 max-w-lg" />
        </div>
        <Skeleton className="h-28 w-full" />
      </div>
    </div>
  );
}
