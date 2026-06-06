import { describe, it, expect, vi } from "vitest"
import { render } from "@testing-library/react"
import { AuthGuard } from "@/components/auth-guard"

vi.mock("next/navigation", () => ({
  useRouter: () => ({
    replace: vi.fn(),
    push: vi.fn(),
  }),
}))

describe("AuthGuard", () => {
  it("renders checking state when not authenticated", () => {
    // localStorage empty → isAuthenticated() returns false → AuthGuard renders spinner
    const { container } = render(
      <AuthGuard>
        <div data-testid="protected">Protected Content</div>
      </AuthGuard>
    )
    expect(container).toBeTruthy()
    // Should show checking spinner, not protected content
    expect(container.querySelector('[data-testid="protected"]')).toBeNull()
  })
})
