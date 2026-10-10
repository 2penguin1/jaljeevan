import { Link, useRouteError } from "react-router";

/** Last-resort boundary: a crashed page still gives the person a way back. */
export function RouteError() {
  const error = useRouteError();
  const message = error instanceof Error ? error.message : "The page failed to load.";
  return (
    <div className="grid min-h-dvh place-items-center px-6">
      <div className="max-w-md">
        <h1 className="font-display text-4xl">This page stopped working</h1>
        <p className="mt-3 text-text-2">{message}</p>
        <Link to="/map" className="mt-6 inline-block rounded border hairline px-4 py-2 hover:bg-raised">
          Go to the live map
        </Link>
      </div>
    </div>
  );
}
