// Toast notification wrapper around Sonner — provides consistent API for success/error/info/warning
// All methods accept message + optional description, promise() tracks async operations

import { toast as sonnerToast } from "sonner"

export const toast = {
  success: (message: string, description?: string) => {
    sonnerToast.success(message, { description })
  },

  error: (message: string, description?: string) => {
    sonnerToast.error(message, { description })
  },

  info: (message: string, description?: string) => {
    sonnerToast(message, { description })
  },

  warning: (message: string, description?: string) => {
    sonnerToast.warning(message, { description })
  },

  loading: (message: string) => {
    return sonnerToast.loading(message)
  },

  dismiss: (id?: string | number) => {
    sonnerToast.dismiss(id)
  },

  promise: <T>(
    promise: Promise<T>,
    options: {
      loading: string
      success: string | ((data: T) => string)
      error: string | ((error: Error) => string)
    }
  ) => {
    return sonnerToast.promise(promise, options)
  },
}
