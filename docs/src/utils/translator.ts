import axios from "axios";

export type TranslatorFieldType = "address" | "item_name" | "person" | "generic";

export interface TranslateItem {
  text: string;
  field_type?: TranslatorFieldType;
}

export interface TranslateBatchRequest {
  source_lang: string;
  target_lang: string;
  items: TranslateItem[];
}

export interface TranslateBatchResponse {
  translations: string[];
}

const TRANSLATOR_BASE_URL =
  process.env.TRANSLATOR_BASE_URL || "http://localhost:8000";

const MAX_ITEMS_PER_REQUEST = Number(process.env.TRANSLATOR_MAX_ITEMS || 50);
const REQUEST_TIMEOUT_MS = Number(process.env.TRANSLATOR_TIMEOUT_MS || 60000);
const CHUNK_SIZE = Number(process.env.TRANSLATOR_CHUNK_SIZE || 20);

function chunkArray<T>(items: T[], chunkSize: number): T[][] {
  const chunks: T[][] = [];
  for (let i = 0; i < items.length; i += chunkSize) {
    chunks.push(items.slice(i, i + chunkSize));
  }
  return chunks;
}

export async function translateBatch(
  payload: TranslateBatchRequest,
): Promise<TranslateBatchResponse> {
  if (!payload.items?.length) {
    return { translations: [] };
  }

  if (payload.items.length > MAX_ITEMS_PER_REQUEST) {
    throw new Error(`Too many translation items. Max allowed: ${MAX_ITEMS_PER_REQUEST}`);
  }

  const response = await axios.post<TranslateBatchResponse>(
    `${TRANSLATOR_BASE_URL}/translate-batch`,
    payload,
    {
      headers: {
        "Content-Type": "application/json",
      },
      timeout: REQUEST_TIMEOUT_MS,
    },
  );

  return response.data;
}

export async function translateEnToJaForLogistics(
  items: TranslateItem[],
): Promise<string[]> {
  if (!items.length) return [];

  const chunks = chunkArray(items, CHUNK_SIZE);
  const allTranslations: string[] = [];

  for (const chunk of chunks) {
    const result = await translateBatch({
      source_lang: "en",
      target_lang: "ja",
      items: chunk,
    });

    allTranslations.push(...result.translations);
  }

  return allTranslations;
}

export function buildLogisticsTranslationItems(input: {
  receiverAddressEn?: string;
  itemNameEn?: string;
  receiverNameEn?: string;
  memoEn?: string;
}) {
  return [
    { text: input.receiverAddressEn || "", field_type: "address" as const },
    { text: input.itemNameEn || "", field_type: "item_name" as const },
    { text: input.receiverNameEn || "", field_type: "person" as const },
    { text: input.memoEn || "", field_type: "generic" as const },
  ];
}
