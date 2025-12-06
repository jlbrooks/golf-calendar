/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './templates/**/*.html',
    './events/templates/**/*.html',
    './events/**/*.py',
  ],
  safelist: [
    // Tour color classes - dynamically generated
    'bg-blue-50/30', 'bg-blue-50', 'bg-blue-500', 'bg-blue-600', 'bg-blue-700',
    'text-blue-700', 'border-blue-200', 'border-blue-400', 'border-blue-600',
    'hover:border-blue-400', 'group-hover:text-blue-700',
    'hover:bg-blue-50', 'hover:text-blue-700', 'hover:border-blue-200',
    'group-hover:bg-blue-600', 'group-hover:text-white', 'group-hover:border-blue-600',
    
    'bg-pink-50/30', 'bg-pink-50', 'bg-pink-500', 'bg-pink-600', 'bg-pink-700',
    'text-pink-700', 'border-pink-200', 'border-pink-400', 'border-pink-600',
    'hover:border-pink-400', 'group-hover:text-pink-700',
    'hover:bg-pink-50', 'hover:text-pink-700', 'hover:border-pink-200',
    'group-hover:bg-pink-600', 'group-hover:text-white', 'group-hover:border-pink-600',
    
    'bg-emerald-50/30', 'bg-emerald-50', 'bg-emerald-500', 'bg-emerald-600', 'bg-emerald-700',
    'text-emerald-700', 'border-emerald-200', 'border-emerald-400', 'border-emerald-600',
    'hover:border-emerald-400', 'group-hover:text-emerald-700',
    'hover:bg-emerald-50', 'hover:text-emerald-700', 'hover:border-emerald-200',
    'group-hover:bg-emerald-600', 'group-hover:text-white', 'group-hover:border-emerald-600',
    
    'bg-slate-50/30', 'bg-slate-50', 'bg-slate-500', 'bg-slate-600', 'bg-slate-700',
    'text-slate-700', 'border-slate-200', 'border-slate-400', 'border-slate-600',
    'hover:border-slate-400', 'group-hover:text-slate-700',
    'hover:bg-slate-50', 'hover:text-slate-700', 'hover:border-slate-200',
    'group-hover:bg-slate-600', 'group-hover:text-white', 'group-hover:border-slate-600',
    
    'bg-purple-50/30', 'bg-purple-50', 'bg-purple-500', 'bg-purple-600', 'bg-purple-700',
    'text-purple-700', 'border-purple-200', 'border-purple-400', 'border-purple-600',
    'hover:border-purple-400', 'group-hover:text-purple-700',
    'hover:bg-purple-50', 'hover:text-purple-700', 'hover:border-purple-200',
    'group-hover:bg-purple-600', 'group-hover:text-white', 'group-hover:border-purple-600',
    
    'bg-gray-50/30', 'bg-gray-50', 'bg-gray-500', 'bg-gray-600', 'bg-gray-700',
    'text-gray-700', 'border-gray-200', 'border-gray-400', 'border-gray-600',
    'hover:border-gray-400', 'group-hover:text-gray-700',
    'hover:bg-gray-50', 'hover:text-gray-700', 'hover:border-gray-200',
    'group-hover:bg-gray-600', 'group-hover:text-white', 'group-hover:border-gray-600',
  ],
  theme: {
    extend: {},
  },
  plugins: [],
}
