"use client";
import React, { useId } from "react";
import s from "./native.module.css";

export default function RumiCompanion({ mood, level = 0 }: { mood: string; level?: number }) {
  const id = useId().replace(/:/g, "");
  return <div className={s.companion} data-mood={mood} role="img" aria-label={`Rumi companion: ${mood}`} style={{ "--voice-level": Math.max(0, Math.min(1, level / 100)) } as React.CSSProperties}>
    <div className={s.aura} /><div className={s.orbit} /><div className={s.orbitTwo} />
    <svg className={s.robot} viewBox="0 0 420 420" aria-hidden="true">
      <defs>
        <linearGradient id={`${id}shell`} x1="0" y1="0" x2="1" y2="1"><stop stopColor="#f1fffd"/><stop offset=".4" stopColor="#8cb9c3"/><stop offset=".72" stopColor="#305a6d"/><stop offset="1" stopColor="#101d35"/></linearGradient>
        <linearGradient id={`${id}visor`} x1="0" y1="0" x2="0" y2="1"><stop stopColor="#0f2535"/><stop offset="1" stopColor="#030911"/></linearGradient>
        <radialGradient id={`${id}core`}><stop stopColor="#eaffff"/><stop offset=".3" stopColor="#80f7e4"/><stop offset="1" stopColor="#207a8b" stopOpacity="0"/></radialGradient>
      </defs>
      <g className={s.body}>
        <path d="M159 249Q210 230 261 249L252 301Q210 331 168 301Z" fill={`url(#${id}shell)`} stroke="#90d2d5" strokeWidth="1.2"/>
        <path d="M177 285Q210 302 243 285" fill="none" stroke="#244b5c"/>
        <circle cx="210" cy="273" r="24" fill={`url(#${id}core)`}/><circle cx="210" cy="273" r="5" fill="#cbfff5"/>
        <g className={s.leftHand}><path d="M145 252Q122 244 117 263L113 287Q128 300 140 282Z" fill={`url(#${id}shell)`}/><path d="m117 277 16 5" stroke="#96ede7"/></g>
        <g className={s.rightHand}><path d="M275 252Q298 244 303 263L307 287Q292 300 280 282Z" fill={`url(#${id}shell)`}/><path d="m303 277-16 5" stroke="#96ede7"/></g>
        <g className={s.head}>
          <path d="M203 109v-22" stroke="#709eab" strokeWidth="4"/><circle className={s.antenna} cx="203" cy="81" r="7" fill="#aafeea"/>
          <path d="M112 153Q111 111 165 106L255 106Q309 111 308 153L304 204Q302 243 253 248H167Q118 243 116 204Z" fill={`url(#${id}shell)`} stroke="#b5e4e4" strokeWidth="1.3"/>
          <path d="M111 161Q95 158 96 179Q96 198 114 195M309 161Q325 158 324 179Q324 198 306 195" fill="#417083" stroke="#91cece"/>
          <path d="M133 152Q133 130 163 128H257Q287 130 287 152V194Q286 224 255 225H165Q134 224 133 194Z" fill={`url(#${id}visor)`} stroke="#194458" strokeWidth="2"/>
          <path d="M149 147Q187 134 225 139" stroke="#3f7081" strokeOpacity=".45" strokeWidth="3" strokeLinecap="round" fill="none"/>
          <g className={s.eyes} fill="#a9fff0"><rect x="158" y="163" width="25" height="33" rx="12"/><rect x="237" y="163" width="25" height="33" rx="12"/></g>
          <path className={s.mouth} d="M199 201q11 9 22 0" fill="none" stroke="#79d9d8" strokeWidth="3" strokeLinecap="round"/>
          <path d="M149 207h12M259 207h12" stroke="#57a5b5" strokeWidth="2" strokeLinecap="round"/>
          <path d="M178 237h64" stroke="#bafaf0" strokeOpacity=".6" strokeWidth="2"/>
        </g>
      </g>
      <ellipse className={s.shadow} cx="210" cy="354" rx="65" ry="7" fill="#49adba" opacity=".12"/>
      <ellipse cx="210" cy="353" rx="110" ry="23" fill="none" stroke="#387488" strokeOpacity=".4"/>
      <ellipse cx="210" cy="353" rx="142" ry="33" fill="none" stroke="#387488" strokeOpacity=".16" strokeDasharray="3 11"/>
    </svg>
  </div>;
}
