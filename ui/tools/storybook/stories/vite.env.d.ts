interface ImportMeta {
  glob: (pattern: string, config: { eager: boolean; as: string }) => Record<string, string>;
}
declare module "*.jpg";
declare module "*.png";
