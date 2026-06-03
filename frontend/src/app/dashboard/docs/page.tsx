"use client"

import { useEffect, useState, useCallback } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { Badge } from "@/components/ui/badge"
import { api } from "@/lib/api"
import { Upload, FileText, Trash2 } from "lucide-react"
import { useDropzone } from "react-dropzone"

interface Document {
  id: string
  filename: string
  file_type: string
  file_size: number
  status: string
  chunk_count: number
  created_at: string
}

export default function DocsPage() {
  const [documents, setDocuments] = useState<Document[]>([])
  const [uploading, setUploading] = useState(false)
  const [loading, setLoading] = useState(true)

  const fetchDocs = async () => {
    try {
      const data = await api.getDocuments()
      setDocuments(data as Document[])
    } catch (err) {
      console.error(err)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    fetchDocs()
  }, [])

  const onDrop = useCallback(async (files: File[]) => {
    setUploading(true)
    for (const file of files) {
      try {
        await api.uploadDocument(file)
      } catch (err) {
        console.error(err)
      }
    }
    setUploading(false)
    fetchDocs()
  }, [])

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: {
      "application/pdf": [".pdf"],
      "text/markdown": [".md"],
      "text/plain": [".txt"],
      "text/html": [".html"],
    },
    maxSize: 50 * 1024 * 1024,
  })

  const handleDelete = async (id: string) => {
    await api.deleteDocument(id)
    fetchDocs()
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight">Documents</h1>
          <p className="text-sm text-muted-foreground">
            Upload PDFs, Markdown, and text files for RAG indexing.
          </p>
        </div>
      </div>

      <div
        {...getRootProps()}
        className={`cursor-pointer rounded-lg border-2 border-dashed p-8 text-center transition-colors ${
          isDragActive ? "border-primary bg-primary/5" : "border-border hover:border-primary/50"
        }`}
      >
        <input {...getInputProps()} />
        <Upload className="mx-auto h-8 w-8 text-muted-foreground" />
        <p className="mt-2 text-sm text-muted-foreground">
          {uploading
            ? "Uploading..."
            : "Drag & drop files here, or click to select (max 50MB)"}
        </p>
      </div>

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {loading
          ? Array(3)
              .fill(null)
              .map((_, i) => (
                <Card key={i} className="animate-pulse">
                  <CardContent className="h-24" />
                </Card>
              ))
          : documents.map((doc) => (
              <Card key={doc.id}>
                <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
                  <CardTitle className="text-sm font-medium truncate">{doc.filename}</CardTitle>
                  <Badge variant={doc.status === "indexed" ? "success" : "warning"}>
                    {doc.status}
                  </Badge>
                </CardHeader>
                <CardContent>
                  <div className="flex items-center gap-2 text-sm text-muted-foreground">
                    <FileText className="h-3 w-3" />
                    <span>{doc.file_type}</span>
                    <span className="text-xs">•</span>
                    <span>{doc.chunk_count} chunks</span>
                  </div>
                  <Button
                    variant="ghost"
                    size="icon"
                    className="ml-auto mt-2"
                    onClick={() => handleDelete(doc.id)}
                  >
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </CardContent>
              </Card>
            ))}
      </div>
    </div>
  )
}
