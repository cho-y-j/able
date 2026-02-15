"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import api from "@/lib/api";
import RecipeCard from "./_components/RecipeCard";
import type { Recipe } from "./types";

export default function RecipesPage() {
  const router = useRouter();
  const [recipes, setRecipes] = useState<Recipe[]>([]);
  const [templates, setTemplates] = useState<Recipe[]>([]);
  const [loading, setLoading] = useState(true);
  const [tab, setTab] = useState<"mine" | "templates">("mine");
  const [alert, setAlert] = useState<{ type: "success" | "error"; message: string } | null>(null);

  useEffect(() => {
    fetchData();
  }, []);

  useEffect(() => {
    if (alert) {
      const timer = setTimeout(() => setAlert(null), 3000);
      return () => clearTimeout(timer);
    }
  }, [alert]);

  const fetchData = async () => {
    try {
      const [recipesRes, templatesRes] = await Promise.all([
        api.get("/recipes"),
        api.get("/recipes/templates"),
      ]);
      setRecipes(recipesRes.data);
      setTemplates(templatesRes.data);
    } catch {
      setAlert({ type: "error", message: "레시피 목록을 불러오지 못했습니다" });
    } finally {
      setLoading(false);
    }
  };

  const handleActivate = async (e: React.MouseEvent, recipe: Recipe) => {
    e.stopPropagation();
    try {
      if (recipe.is_active) {
        await api.post(`/recipes/${recipe.id}/deactivate`);
        setAlert({ type: "success", message: `"${recipe.name}" 비활성화됨` });
      } else {
        await api.post(`/recipes/${recipe.id}/activate`);
        setAlert({ type: "success", message: `"${recipe.name}" 활성화됨` });
      }
      fetchData();
    } catch {
      setAlert({ type: "error", message: "상태 변경에 실패했습니다" });
    }
  };

  const handleDelete = async (e: React.MouseEvent, recipe: Recipe) => {
    e.stopPropagation();
    if (!confirm("이 레시피를 삭제하시겠습니까?")) return;
    try {
      await api.delete(`/recipes/${recipe.id}`);
      setAlert({ type: "success", message: `"${recipe.name}" 삭제됨` });
      fetchData();
    } catch {
      setAlert({ type: "error", message: "삭제에 실패했습니다" });
    }
  };

  const handleClone = async (id: string) => {
    try {
      const { data } = await api.post(`/recipes/${id}/clone`);
      setAlert({ type: "success", message: "레시피가 복제되었습니다" });
      router.push(`/dashboard/recipes/${data.id}`);
    } catch {
      setAlert({ type: "error", message: "복제에 실패했습니다" });
    }
  };

  const activeCount = recipes.filter((r) => r.is_active).length;

  return (
    <div className="space-y-6">
      {/* Alert */}
      {alert && (
        <div
          className={`px-4 py-3 rounded-lg text-sm font-medium ${
            alert.type === "success"
              ? "bg-green-500/10 border border-green-500/30 text-green-400"
              : "bg-red-500/10 border border-red-500/30 text-red-400"
          }`}
        >
          {alert.message}
        </div>
      )}

      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">나만의 기법</h1>
          <p className="text-gray-400 text-sm mt-1">
            여러 알고리즘을 조합하여 나만의 자동매매 전략을 만드세요
          </p>
        </div>
        <div className="flex gap-2">
          <button
            onClick={() => router.push("/dashboard/recipes/monitor")}
            className="bg-green-600 hover:bg-green-700 text-white px-4 py-2.5 rounded-lg text-sm font-medium transition-colors flex items-center gap-2"
          >
            <span className="relative flex h-2 w-2">
              <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-green-300 opacity-75" />
              <span className="relative inline-flex rounded-full h-2 w-2 bg-green-400" />
            </span>
            실시간 모니터
          </button>
          <button
            onClick={() => router.push("/dashboard/recipes/new")}
            className="bg-blue-600 hover:bg-blue-700 text-white px-4 py-2.5 rounded-lg text-sm font-medium transition-colors flex items-center gap-2"
          >
            <span className="text-lg">+</span>
            새 레시피 만들기
          </button>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-3 gap-4">
        <div className="bg-gray-800 rounded-xl p-4 border border-gray-700">
          <p className="text-gray-400 text-xs">전체 레시피</p>
          <p className="text-2xl font-bold text-white mt-1">{recipes.length}</p>
        </div>
        <div className="bg-gray-800 rounded-xl p-4 border border-gray-700">
          <p className="text-gray-400 text-xs">활성 레시피</p>
          <p className="text-2xl font-bold text-green-400 mt-1">{activeCount}</p>
        </div>
        <div className="bg-gray-800 rounded-xl p-4 border border-gray-700">
          <p className="text-gray-400 text-xs">템플릿</p>
          <p className="text-2xl font-bold text-purple-400 mt-1">{templates.length}</p>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 bg-gray-800 p-1 rounded-lg w-fit">
        <button
          onClick={() => setTab("mine")}
          className={`px-4 py-2 rounded-md text-sm transition-colors ${
            tab === "mine"
              ? "bg-blue-600 text-white"
              : "text-gray-400 hover:text-white"
          }`}
        >
          내 레시피 ({recipes.length})
        </button>
        <button
          onClick={() => setTab("templates")}
          className={`px-4 py-2 rounded-md text-sm transition-colors ${
            tab === "templates"
              ? "bg-blue-600 text-white"
              : "text-gray-400 hover:text-white"
          }`}
        >
          템플릿 갤러리 ({templates.length})
        </button>
      </div>

      {/* Content */}
      {loading ? (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {[1, 2, 3].map((i) => (
            <div key={i} className="bg-gray-800 rounded-xl p-5 border border-gray-700 animate-pulse">
              <div className="h-5 bg-gray-700 rounded w-2/3 mb-3" />
              <div className="h-4 bg-gray-700 rounded w-full mb-2" />
              <div className="h-4 bg-gray-700 rounded w-1/2" />
            </div>
          ))}
        </div>
      ) : tab === "mine" ? (
        recipes.length === 0 ? (
          <div className="text-center py-16 bg-gray-800/50 rounded-xl border border-gray-700 border-dashed">
            <p className="text-gray-400 text-lg mb-2">아직 레시피가 없습니다</p>
            <p className="text-gray-500 text-sm mb-6">
              여러 알고리즘을 조합하여 나만의 전략을 만들어 보세요
            </p>
            <button
              onClick={() => router.push("/dashboard/recipes/new")}
              className="bg-blue-600 hover:bg-blue-700 text-white px-6 py-2.5 rounded-lg text-sm font-medium transition-colors"
            >
              첫 레시피 만들기
            </button>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {recipes.map((recipe) => (
              <RecipeCard
                key={recipe.id}
                recipe={recipe}
                onClick={() => router.push(`/dashboard/recipes/${recipe.id}`)}
                onActivate={(e) => handleActivate(e, recipe)}
                onDelete={(e) => handleDelete(e, recipe)}
              />
            ))}
          </div>
        )
      ) : templates.length === 0 ? (
        <div className="text-center py-16 bg-gray-800/50 rounded-xl border border-gray-700 border-dashed">
          <p className="text-gray-400">아직 공유된 템플릿이 없습니다</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {templates.map((tmpl) => (
            <div
              key={tmpl.id}
              className="bg-gray-800 border border-gray-700 rounded-xl p-5 hover:border-purple-500/50 transition-colors"
            >
              <h3 className="text-white font-semibold">{tmpl.name}</h3>
              {tmpl.description && (
                <p className="text-gray-400 text-sm mt-1 line-clamp-2">{tmpl.description}</p>
              )}
              <div className="flex flex-wrap gap-2 mt-3 mb-4">
                <span className="bg-purple-500/20 text-purple-400 text-xs px-2 py-1 rounded-full">
                  {tmpl.signal_config?.signals?.length || 0}개 시그널
                </span>
                <span className="bg-gray-700 text-gray-300 text-xs px-2 py-1 rounded-full">
                  {tmpl.signal_config?.combinator || "AND"}
                </span>
              </div>
              <button
                onClick={() => handleClone(tmpl.id)}
                className="w-full bg-purple-600/20 text-purple-400 hover:bg-purple-600/30 py-2 rounded-lg text-sm transition-colors"
              >
                내 레시피로 복제
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
