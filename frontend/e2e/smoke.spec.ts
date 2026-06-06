import { test, expect } from "@playwright/test"

test("login page loads", async ({ page }) => {
  await page.goto("/login")
  await expect(page.locator("text=Flux Gateway")).toBeVisible()
  await expect(page.locator("text=Sign in to access your dashboard")).toBeVisible()
})

test("login page has API key form", async ({ page }) => {
  await page.goto("/login")
  const input = page.locator('input[type="password"]')
  await expect(input).toBeVisible()
  const button = page.locator('button:has-text("Verify")')
  await expect(button).toBeVisible()
})
