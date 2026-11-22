import { defineConfig, globalIgnores } from "eslint/config";
import nextVitals from "eslint-config-next/core-web-vitals";
import nextTs from "eslint-config-next/typescript";

const eslintConfig = defineConfig([
  ...nextVitals,
  ...nextTs,
  {
    // These folders are Lovable's pages and components ported one-to-one. Lovable's own lint setup didn't
    // run the React Compiler advisory rules or the apostrophe rule, and the code works as written, so
    // they're off here rather than rewriting the ported UI.
    files: ["components/pages/**", "components/casino/**", "components/games/**", "components/zg/**"],
    linterOptions: { reportUnusedDisableDirectives: "off" },
    rules: {
      "react/no-unescaped-entities": "off",
      "react-hooks/set-state-in-effect": "off",
      "react-hooks/purity": "off",
      "react-hooks/preserve-manual-memoization": "off",
      "react-hooks/exhaustive-deps": "off",
      "@typescript-eslint/no-unused-vars": "off",
    },
  },
  // Override default ignores of eslint-config-next.
  globalIgnores([
    // Default ignores of eslint-config-next:
    ".next/**",
    "out/**",
    "build/**",
    "next-env.d.ts",
  ]),
]);

export default eslintConfig;
