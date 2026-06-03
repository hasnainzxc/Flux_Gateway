// Root page — immediately redirects to /dashboard (no landing page yet)

import { redirect } from "next/navigation"

export default function RootPage() {
  redirect("/dashboard")
}
