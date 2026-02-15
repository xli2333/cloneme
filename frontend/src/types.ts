export type Role = 'user' | 'assistant'

export interface Bubble {
  text: string
  delay_ms: number
}

export interface ChatResponse {
  conversation_id: string
  user_message_id: number
  assistant_message_ids: number[]
  bubbles: Bubble[]
  debug: Record<string, unknown>
}

export interface MessageDTO {
  id: number
  role: Role
  content: string
  created_at: string
  message_type: string
  feedback_score: number
}

export interface ConversationResponse {
  conversation_id: string
  messages: MessageDTO[]
}

export interface FeedbackResponse {
  ok: boolean
  accepted_count: number
  preference_version: number
  summary: string
}

export interface ConversationMeta {

  id: string

  title: string

  preview: string

  updatedAt: number

}



export interface SearchResultDTO {

  id: number

  conversation_id: string

  role: Role

  content: string

  created_at: string

}



export interface SearchResponse {

  query: string

  results: SearchResultDTO[]

}


