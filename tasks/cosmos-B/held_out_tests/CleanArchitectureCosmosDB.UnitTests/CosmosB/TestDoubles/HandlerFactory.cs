using AutoMapper;
using CleanArchitectureCosmosDB.Core.Entities;
using CleanArchitectureCosmosDB.WebAPI.Models.ToDoItem;
using Microsoft.Extensions.Logging;
using Microsoft.Extensions.Logging.Abstractions;
using System;
using System.Linq;
using System.Reflection;

namespace CleanArchitectureCosmosDB.UnitTests.CosmosB.TestDoubles
{
    /// <summary>
    ///     Constructs a handler through its public constructor, supplying whatever
    ///     cross-cutting collaborators it asks for (repository, IMapper, ILogger).
    ///     The ticket pins the handler's behaviour, not its constructor shape —
    ///     the existing Create/Delete slices inject IMapper, so a solution that
    ///     follows that convention must grade the same as one that does not.
    /// </summary>
    public static class HandlerFactory
    {
        public static T Create<T>(object repo)
        {
            ConstructorInfo ctor = typeof(T).GetConstructors()
                .OrderBy(c => c.GetParameters().Length)
                .First();
            object[] args = ctor.GetParameters()
                .Select(p => Resolve(p.ParameterType, repo))
                .ToArray();
            return (T)ctor.Invoke(args);
        }

        private static object Resolve(Type type, object repo)
        {
            if (type.IsInstanceOfType(repo))
            {
                return repo;
            }
            if (type == typeof(IMapper))
            {
                MapperConfiguration config = new MapperConfiguration(cfg =>
                    cfg.CreateMap<ToDoItem, ToDoItemModel>());
                return config.CreateMapper();
            }
            if (type.IsGenericType && type.GetGenericTypeDefinition() == typeof(ILogger<>))
            {
                Type nullLogger = typeof(NullLogger<>).MakeGenericType(type.GetGenericArguments());
                return nullLogger.GetField("Instance", BindingFlags.Public | BindingFlags.Static)?.GetValue(null)
                    ?? Activator.CreateInstance(nullLogger);
            }
            if (type == typeof(ILogger))
            {
                return NullLogger.Instance;
            }
            return null;
        }
    }
}
