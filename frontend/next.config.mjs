/** @type {import('next').NextConfig} */
const CONFIGURED_API = process.env.NEXT_PUBLIC_API_URL;

const nextConfig = {
  reactStrictMode: true,

  // In development the API is proxied so the browser makes same-origin requests and
  // nothing needs CORS configuration on a reviewer's machine.
  //
  // In production NEXT_PUBLIC_API_URL is set, lib/api.ts calls the backend directly,
  // and this rewrite is not used — but it is kept as a same-origin fallback so a
  // deployment with the variable missing degrades to a clear "cannot reach the API"
  // message rather than silently requesting paths that do not exist.
  async rewrites() {
    return [
      {
        source: "/api/:path*",
        destination: `${CONFIGURED_API || "http://127.0.0.1:8000"}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
