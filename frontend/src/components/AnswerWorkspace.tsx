'use client';

import React, { useState, useEffect, useRef } from 'react';
import Link from 'next/link';
import {
  ShieldCheck,
  ExternalLink,
  FileText,
  AlertTriangle,
  CheckCircle2,
  Bookmark,
  GitCompare,
  Download,
  Info,
  Cpu,
  Layers,
  Sparkles,
  Volume2,
  Square,
} from 'lucide-react';
import { APIQueryResponse, getDocumentUrl } from '@/lib/api';
import { speakText, stopSpeaking } from '@/lib/voice';

interface AnswerWorkspaceProps {
  query: string;
  response: APIQueryResponse;
  onSaveResearch?: () => void;
}

const LANG_NAME_MAP: Record<string, string> = {
  en: 'English',
  te: 'Telugu',
  hi: 'Hindi',
  kn: 'Kannada',
  ta: 'Tamil',
  bn: 'Bengali',
  mr: 'Marathi',
  ml: 'Malayalam',
  gu: 'Gujarati',
  pa: 'Punjabi',
  or: 'Odia',
  as: 'Assamese',
  ur: 'Urdu',
  sa: 'Sanskrit',
};

function getOriginalQueryLanguage(queryText: string, explicitUserLang?: string | null): string | null {
  if (!queryText || !queryText.trim()) return null;
  const raw = queryText.trim();

  // 1. Script checks for Indic & Non-English Unicode ranges
  if (/[\u0c00-\u0c7f]/.test(raw)) return 'te';
  if (/[\u0c80-\u0cff]/.test(raw)) return 'kn';
  if (/[\u0900-\u097f]/.test(raw)) return 'hi';
  if (/[\u0b80-\u0bff]/.test(raw)) return 'ta';
  if (/[\u0980-\u09ff]/.test(raw)) return 'bn';
  if (/[\u0a80-\u0aff]/.test(raw)) return 'gu';
  if (/[\u0a00-\u0a7f]/.test(raw)) return 'pa';
  if (/[\u0b00-\u0b7f]/.test(raw)) return 'or';
  if (/[\u0d00-\u0d7f]/.test(raw)) return 'ml';
  if (/[\u0600-\u06ff]/.test(raw)) return 'ur';
  if (/[\u0900-\u0d7f\u0600-\u06ff]/.test(raw)) return 'non-en';

  // 2. Explicit non-English selection (e.g. Tenglish/Hinglish in Latin script)
  if (explicitUserLang && explicitUserLang !== 'en') {
    return explicitUserLang;
  }

  // 3. Fail-closed ASCII check for English
  const isAscii = /^[\x00-\x7F]+$/.test(raw);
  if (!isAscii) {
    return null;
  }

  return 'en';
}

export default function AnswerWorkspace({
  query,
  response,
  onSaveResearch,
}: AnswerWorkspaceProps) {
  const [isSpeakingState, setIsSpeakingState] = useState<boolean>(false);
  const lastSpokenIdRef = useRef<string>('');

  // Extract internal Cosine Similarity score from backend vector retrieval
  let rawCosineSim: number | null = null;
  if (typeof response.cosine_similarity === 'number' && !isNaN(response.cosine_similarity)) {
    rawCosineSim = response.cosine_similarity;
  } else if (Array.isArray(response.evidence) && response.evidence.length > 0) {
    const topFaissScore = (response.evidence[0] as any)?.faiss_score;
    if (typeof topFaissScore === 'number' && !isNaN(topFaissScore)) {
      rawCosineSim = topFaissScore;
    }
  }

  // Extract Confidence metrics & compute combined score if not pre-combined
  const rawConfScore = typeof response.confidence_score === 'number' && !isNaN(response.confidence_score)
    ? response.confidence_score
    : (typeof response.confidence === 'number' && !isNaN(response.confidence) ? response.confidence : null);

  let fusedConf: number;
  if (rawConfScore !== null && rawCosineSim !== null && !isNaN(rawConfScore) && !isNaN(rawCosineSim)) {
    const normCos = Math.max(0, Math.min(1, rawCosineSim));
    const normConf = Math.max(0, Math.min(1, rawConfScore));
    fusedConf = (0.5 * normCos) + (0.5 * normConf);
  } else if (rawConfScore !== null && !isNaN(rawConfScore)) {
    fusedConf = Math.max(0, Math.min(1, rawConfScore));
  } else if (rawCosineSim !== null && !isNaN(rawCosineSim)) {
    fusedConf = Math.max(0, Math.min(1, rawCosineSim));
  } else {
    fusedConf = 0;
  }

  const confPct = typeof response.confidence_percentage === 'number' && !isNaN(response.confidence_percentage)
    ? Math.round(response.confidence_percentage)
    : Math.round(fusedConf * 100);

  // Hard safety guard: guarantee never NaN, undefined, or Infinity
  const safeConfPct = isNaN(confPct) || !isFinite(confPct) ? 0 : Math.max(0, Math.min(100, confPct));

  const confLevel = response.confidence_level || (safeConfPct >= 90 ? 'HIGH' : safeConfPct >= 70 ? 'MEDIUM' : 'LOW');
  const isAbstained = Boolean(response.is_abstention || response.confidence_should_abstain);

  // Extract key findings bullet points from answer if available
  const keyFindings = response.answer
    ? response.answer
        .split('\n')
        .filter((line) => line.trim().length > 20 && !line.startsWith('['))
        .slice(0, 3)
    : [];

  const userLangFromResponse = (response as any).user_language || (response as any).detected_language;
  const queryLang = getOriginalQueryLanguage(query, userLangFromResponse);
  const isEnglishQuery = queryLang === 'en';
  const displayLangName = (queryLang && LANG_NAME_MAP[queryLang]) || 'English';

  const answerId = response.answer ? `${query}_${response.answer.slice(0, 50)}` : '';

  // Automatic Speech Synthesis on NEW Answer (English queries only)
  useEffect(() => {
    if (!isEnglishQuery) {
      stopSpeaking();
      setIsSpeakingState(false);
      return;
    }

    if (answerId && lastSpokenIdRef.current !== answerId && isEnglishQuery) {
      lastSpokenIdRef.current = answerId;

      speakText({
        text: response.answer || '',
        lang: 'en',
        queryText: query,
        onStart: () => setIsSpeakingState(true),
        onEnd: () => setIsSpeakingState(false),
        onError: () => setIsSpeakingState(false),
      });
    }

    return () => {
      stopSpeaking();
      setIsSpeakingState(false);
    };
  }, [answerId, response.answer, isEnglishQuery, query]);

  const toggleSpeech = () => {
    if (!isEnglishQuery) {
      stopSpeaking();
      setIsSpeakingState(false);
      return;
    }
    if (isSpeakingState) {
      stopSpeaking();
      setIsSpeakingState(false);
    } else {
      speakText({
        text: response.answer || '',
        lang: 'en',
        queryText: query,
        onStart: () => setIsSpeakingState(true),
        onEnd: () => setIsSpeakingState(false),
        onError: () => setIsSpeakingState(false),
      });
    }
  };

  return (
    <div className="space-y-6 my-6 relative z-10 font-sans-body">
      {/* 1. RESEARCH QUESTION HEADER */}
      <div className="bg-white border border-[#C8D7C2] rounded-xl p-5 shadow-xs">
        <div className="flex flex-wrap items-center justify-between gap-3 mb-2 border-b border-[#C8D7C2]/60 pb-3">
          <div className="text-[11px] font-bold text-[#003E29] uppercase tracking-wider">
            RESEARCH QUESTION
          </div>

          <div className="flex items-center gap-2">
            {/* Detected Language */}
            <span className="bg-[#EEF3E4] text-[#003E29] text-[11px] font-semibold px-2.5 py-0.5 rounded border border-[#C8D7C2]">
              Language: {displayLangName} / Auto-Detected
            </span>

            {/* Invoked Agents / Category */}
            {response.agents_invoked?.map((agent, idx) => {
              const agentLabel =
                typeof agent === 'string'
                  ? agent
                  : typeof agent === 'object' && agent !== null
                  ? (agent as any).name || (agent as any).value || String(agent)
                  : String(agent);

              return (
                <span
                  key={idx}
                  className="bg-[#EEF3E4] text-[#003E29] text-[11px] font-semibold px-2.5 py-0.5 rounded border border-[#C8D7C2]"
                >
                  {agentLabel}
                </span>
              );
            })}

            {/* Combined Grounded Confidence Badge (Retrieval Relevance + Bayesian Assessment) */}
            <div
              className={`flex items-center gap-1.5 text-xs font-semibold px-3 py-1 rounded-md shadow-xs border ${
                isAbstained
                  ? 'bg-amber-100 text-amber-900 border-amber-300'
                  : confLevel === 'HIGH'
                  ? 'bg-emerald-100 text-emerald-900 border-emerald-300'
                  : confLevel === 'MEDIUM'
                  ? 'bg-blue-100 text-blue-900 border-blue-300'
                  : 'bg-amber-100 text-amber-900 border-amber-300'
              }`}
              title="Grounded Confidence: Combined Retrieval Cosine Similarity & Bayesian Confidence Assessment"
            >
              <Sparkles className="w-3.5 h-3.5 text-[#003E29]" />
              <span>Confidence: {safeConfPct}%</span>
              <span className="text-[10px] font-bold uppercase tracking-wider px-1.5 py-0.2 bg-white/70 rounded border border-black/10">
                {isAbstained ? 'ABSTAINED' : confLevel}
              </span>
            </div>
          </div>
        </div>

        <p className="text-base font-serif-heading font-bold text-[#003E29]">
          "{query}"
        </p>
      </div>

      {/* 2. RESEARCH PROCESS BAR (High Level) */}
      <div className="bg-white border border-[#C8D7C2] rounded-xl p-4 shadow-xs text-xs text-[#385246]">
        <div className="flex items-center gap-2 font-bold text-[#003E29] mb-2 uppercase tracking-wider text-[11px]">
          <Cpu className="w-3.5 h-3.5 text-[#003E29]" />
          <span>RESEARCH PROCESS TRACKER</span>
        </div>

        <div className="flex flex-wrap items-center gap-2 text-[11px] font-medium">
          <span className="flex items-center gap-1 bg-emerald-50 text-emerald-900 px-2 py-1 rounded border border-emerald-200">
            <CheckCircle2 className="w-3 h-3 text-emerald-600" /> Language Detection
          </span>
          <span className="text-gray-300">→</span>
          <span className="flex items-center gap-1 bg-emerald-50 text-emerald-900 px-2 py-1 rounded border border-emerald-200">
            <CheckCircle2 className="w-3 h-3 text-emerald-600" /> Query Normalization
          </span>
          <span className="text-gray-300">→</span>
          <span className="flex items-center gap-1 bg-emerald-50 text-emerald-900 px-2 py-1 rounded border border-emerald-200">
            <CheckCircle2 className="w-3 h-3 text-emerald-600" /> Hybrid FAISS + BM25 RAG
          </span>
          <span className="text-gray-300">→</span>
          <span className="flex items-center gap-1 bg-emerald-50 text-emerald-900 px-2 py-1 rounded border border-emerald-200">
            <CheckCircle2 className="w-3 h-3 text-emerald-600" /> RRF Fusion
          </span>
          <span className="text-gray-300">→</span>
          <span className="flex items-center gap-1 bg-emerald-50 text-emerald-900 px-2 py-1 rounded border border-emerald-200">
            <CheckCircle2 className="w-3 h-3 text-emerald-600" /> Citation Validation
          </span>
          <span className="text-gray-300">→</span>
          <span className="flex items-center gap-1 bg-emerald-50 text-emerald-900 px-2 py-1 rounded border border-emerald-200">
            <CheckCircle2 className="w-3 h-3 text-emerald-600" /> Bayesian Confidence
          </span>
        </div>
      </div>

      {/* 3. MAIN ANSWER SYNTHESIS */}
      <div className="bg-white border border-[#C8D7C2] rounded-xl p-6 shadow-xs space-y-4">
        <div className="flex items-center justify-between border-b border-[#C8D7C2]/60 pb-3">
          <div>
            <h2 className="font-serif-heading text-2xl font-bold text-[#003E29]">
              Research Synthesis & Answer
            </h2>
            <div className="text-xs text-[#385246] mt-0.5">
              Grounded in verified statutory provisions and Traditional Knowledge archives
            </div>
          </div>

          {/* Accessible Speaker / Stop Control (English responses only) */}
          {isEnglishQuery && (
            <button
              type="button"
              onClick={toggleSpeech}
              className={`flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold border transition-all cursor-pointer ${
                isSpeakingState
                  ? 'bg-red-50 text-red-600 border-red-200 hover:bg-red-100'
                  : 'bg-[#EEF3E4] hover:bg-[#E3EBD7] text-[#003E29] border-[#C8D7C2]'
              }`}
              title={isSpeakingState ? 'Stop reading answer aloud' : 'Read answer aloud (English)'}
              aria-label={isSpeakingState ? 'Stop reading answer' : 'Read answer'}
            >
              {isSpeakingState ? (
                <>
                  <Square className="w-3.5 h-3.5 fill-red-600 text-red-600" />
                  <span>Stop</span>
                </>
              ) : (
                <>
                  <Volume2 className="w-3.5 h-3.5 text-[#003E29]" />
                  <span>Speak</span>
                </>
              )}
            </button>
          )}
        </div>

        <div className="text-sm text-[#1A2E26] leading-relaxed whitespace-pre-wrap font-sans-body">
          {response.answer}
        </div>

        {/* Abstention Banner */}
        {response.is_abstention && (
          <div className="bg-amber-50 border-l-4 border-amber-500 p-4 rounded-r-lg text-xs text-amber-900 flex items-start gap-2.5">
            <AlertTriangle className="w-4 h-4 text-amber-600 shrink-0 mt-0.5" />
            <div>
              <div className="font-semibold mb-0.5">Human / IP Facilitator Escalation Recommended</div>
              <div>Evidence threshold was insufficient for a conclusive decision. Consult an IP Facilitator or AYUSH authority.</div>
            </div>
          </div>
        )}
      </div>

      {/* 4. KEY FINDINGS */}
      {keyFindings.length > 0 && (
        <div className="bg-[#FFFFFF] border border-[#C8D7C2] rounded-xl p-5 shadow-xs space-y-3">
          <div className="flex items-center gap-2 font-serif-heading text-lg font-bold text-[#003E29]">
            <Sparkles className="w-4 h-4 text-[#003E29]" />
            <span>Key Findings</span>
          </div>
          <ul className="space-y-2 text-xs text-[#263A35]">
            {keyFindings.map((finding, idx) => (
              <li key={idx} className="flex items-start gap-2 bg-[#FAFDF6] p-2.5 rounded-lg border border-[#C8D7C2]/50">
                <span className="font-bold text-[#003E29]">•</span>
                <span className="leading-relaxed">{finding}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* 5. GROUNDED EVIDENCE CARDS */}
      {response.evidence && response.evidence.length > 0 && (
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <h3 className="font-serif-heading text-xl font-bold text-[#003E29]">
              Grounded Source Evidence ({response.evidence.length})
            </h3>
            <span className="text-xs text-[#385246]">RRF Fusion Grounded</span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {response.evidence.map((item, index) => {
              const rawUrl = item.source_url || (item as any).url;
              const isWebSource = Boolean(
                item.source_id?.startsWith('web-') ||
                item.source_id?.startsWith('live-') ||
                (rawUrl && rawUrl.startsWith('http') && !rawUrl.includes('/document/'))
              );
              
              const docUrl = rawUrl && rawUrl.startsWith('http') ? rawUrl : item.source_id ? getDocumentUrl(item.source_id) : '#';
              const hasValidUrl = docUrl && docUrl !== '#';

              return (
                <div
                  key={index}
                  className="bg-white border border-[#C8D7C2] rounded-xl p-4 shadow-xs hover:shadow-md transition-shadow flex flex-col justify-between"
                >
                  <div>
                    <div className="flex items-center justify-between gap-2 mb-2">
                      <span
                        className={`text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded border ${
                          isWebSource
                            ? 'bg-blue-50 text-blue-800 border-blue-200'
                            : 'bg-emerald-50 text-emerald-800 border-emerald-200'
                        }`}
                      >
                        {isWebSource ? '🌐 LIVE WEB SOURCE' : '📜 INTERNAL KNOWLEDGE BASE'}
                      </span>
                      <span className="font-mono text-[10px] font-bold bg-[#EEF3E4] text-[#003E29] px-2 py-0.5 rounded border border-[#C8D7C2]">
                        SOURCE {index + 1}
                      </span>
                    </div>

                    <div className="font-serif-heading font-bold text-sm text-[#003E29] leading-snug mb-1">
                      {item.title}
                    </div>

                    <div className="text-[11px] font-semibold text-[#385246] mb-2 flex flex-wrap items-center gap-1.5">
                      <span>{item.authority || 'Government Authority'}</span>
                      {item.source_name && item.source_name !== item.title && (
                        <span>· {item.source_name}</span>
                      )}
                      {item.jurisdiction && (
                        <span className="bg-gray-100 text-gray-700 text-[10px] px-1.5 py-0.2 rounded">
                          {item.jurisdiction}
                        </span>
                      )}
                    </div>

                    <p className="text-xs text-[#263A35] leading-relaxed bg-[#FAFDF6] p-3 rounded-lg border border-[#C8D7C2]/50 italic">
                      "{item.content}"
                    </p>
                  </div>

                  <div className="mt-3 pt-2 border-t border-[#C8D7C2]/40 flex justify-end">
                    {hasValidUrl ? (
                      <a
                        href={docUrl}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="inline-flex items-center gap-1 text-xs font-semibold text-[#003E29] hover:underline"
                      >
                        <FileText className="w-3.5 h-3.5 text-[#003E29]" />
                        <span>View Original Source ↗</span>
                        <ExternalLink className="w-3 h-3" />
                      </a>
                    ) : (
                      <span className="text-[11px] text-gray-400 italic">Source link unavailable</span>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      )}

      {/* 6. SOURCES & CITATIONS */}
      {response.citations && response.citations.length > 0 && (
        <div className="bg-white border border-[#C8D7C2] rounded-xl p-4 text-xs text-[#385246]">
          <div className="font-bold text-[#003E29] uppercase tracking-wider text-[11px] mb-2">
            OFFICIAL CITATIONS & SOURCES
          </div>
          <div className="flex flex-wrap gap-2">
            {response.citations.map((cite, i) => {
              const label =
                typeof cite === 'string'
                  ? cite
                  : typeof cite === 'object' && cite !== null
                  ? (cite as any).source_label
                    ? `${(cite as any).source_label}${(cite as any).claim_snippet ? `: ${(cite as any).claim_snippet}` : ''}`
                    : (cite as any).claim_snippet || JSON.stringify(cite)
                  : String(cite);

              return (
                <span
                  key={i}
                  className="bg-[#EEF3E4] border border-[#C8D7C2] text-[#003E29] px-2.5 py-1 rounded text-[11px] font-medium"
                >
                  {label}
                </span>
              );
            })}
          </div>
        </div>
      )}

      {/* 7. ACTION BUTTONS ROW */}
      <div className="flex flex-wrap items-center justify-between gap-3 bg-white border border-[#C8D7C2] rounded-xl p-4 shadow-xs">
        <div className="text-xs font-semibold text-[#003E29]">
          Research Actions
        </div>

        <div className="flex flex-wrap gap-2">
          <button
            onClick={onSaveResearch || (() => alert('Research saved to your history.'))}
            className="flex items-center gap-1.5 bg-[#EEF3E4] hover:bg-[#E3EBD7] text-[#003E29] text-xs font-semibold px-3.5 py-2 rounded-lg border border-[#C8D7C2] transition-colors cursor-pointer"
          >
            <Bookmark className="w-3.5 h-3.5" />
            <span>Save Research</span>
          </button>

          <Link
            href="/brief"
            className="flex items-center gap-1.5 bg-[#EEF3E4] hover:bg-[#E3EBD7] text-[#003E29] text-xs font-semibold px-3.5 py-2 rounded-lg border border-[#C8D7C2] transition-colors"
          >
            <FileText className="w-3.5 h-3.5" />
            <span>Generate Brief</span>
          </Link>

          <Link
            href="/compare"
            className="flex items-center gap-1.5 bg-[#003E29] hover:bg-[#044D34] text-white text-xs font-semibold px-3.5 py-2 rounded-lg shadow-sm transition-colors"
          >
            <GitCompare className="w-3.5 h-3.5" />
            <span>Compare Jurisdictions</span>
          </Link>
        </div>
      </div>

      {/* Disclaimer Note */}
      {response.disclaimer && (
        <div className="text-[11px] text-[#385246] italic leading-relaxed pt-2">
          {response.disclaimer}
        </div>
      )}
    </div>
  );
}
